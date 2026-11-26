"""Tests of the FES2014 reader for water levels and tidal currents (synthetic files)."""

import datetime
import os

import numpy as np
import pytest
import xarray as xr

from cht_tide.export import export_map, predict_at_point, read_box
from cht_tide.fes2014 import TideModelFes2014

LON = np.arange(
    0.0, 360.0, 0.125
)  # fine enough for the 0.25 degree padding of get_data_on_points
LAT = np.arange(-10.0, 10.5, 1.0)

# amplitude (cm or cm/s) and phase (degrees) per quantity and constituent
VALUES = {
    "z": {"m2": (100.0, 10.0), "s2": (50.0, 20.0)},
    "u": {"m2": (40.0, 100.0), "s2": (20.0, 110.0)},
    "v": {"m2": (30.0, 200.0), "s2": (10.0, 210.0)},
}
FOLDERS = {
    "z": ("", "amplitude", "phase"),
    "u": ("eastward_velocity", "Ua", "Ug"),
    "v": ("northward_velocity", "Va", "Vg"),
}


def _write_model(path, currents=True):
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, "metadata.tml"), "w") as f:
        f.write('longname = "synthetic FES"\nformat = "fes2014"\n')
    shape = (LAT.size, LON.size)
    for quantity in ("z", "u", "v") if currents else ("z",):
        folder, amp_name, phase_name = FOLDERS[quantity]
        os.makedirs(os.path.join(path, folder), exist_ok=True)
        for constituent, (amp, phase) in VALUES[quantity].items():
            ds = xr.Dataset(
                {
                    amp_name: (("lat", "lon"), np.full(shape, amp, "f4")),
                    phase_name: (("lat", "lon"), np.full(shape, phase, "f4")),
                },
                coords={"lat": LAT, "lon": LON},
            )
            ds.to_netcdf(os.path.join(path, folder, f"{constituent}.nc"))
    return TideModelFes2014("synthetic", str(path))


def test_has_currents(tmp_path):
    assert _write_model(tmp_path / "with").has_currents
    assert not _write_model(tmp_path / "without", currents=False).has_currents


@pytest.mark.parametrize("quantity", ["z", "u", "v"])
def test_get_data(tmp_path, quantity):
    model = _write_model(tmp_path)
    ds = model.get_data(
        [2.0, 4.0], [-1.0, 1.0], constituents=["m2", "s2"], quantity=quantity
    )
    assert ds.amplitude.shape == (2, 3, 17)
    for i, c in enumerate(["m2", "s2"]):
        amp, phase = VALUES[quantity][c]
        np.testing.assert_allclose(ds.amplitude.values[i], amp / 100.0, rtol=1e-6)
        np.testing.assert_allclose(ds.phase.values[i], phase, rtol=1e-6)


def test_default_quantity_is_water_level(tmp_path):
    model = _write_model(tmp_path)
    ds = model.get_data([2.0, 4.0], [-1.0, 1.0], constituents=["m2"])
    np.testing.assert_allclose(ds.amplitude.values, 1.0)


def test_no_currents_raises(tmp_path):
    model = _write_model(tmp_path, currents=False)
    with pytest.raises(ValueError, match="no tidal currents"):
        model.get_data([2.0, 4.0], [-1.0, 1.0], quantity="u")
    with pytest.raises(ValueError, match="no tidal currents"):
        model.get_data_on_points(x=[3.0], y=[0.0], crs=4326, quantity="v")


def test_unknown_quantity_raises(tmp_path):
    model = _write_model(tmp_path)
    with pytest.raises(ValueError, match="Unknown quantity"):
        model.get_data([2.0, 4.0], [-1.0, 1.0], quantity="w")


def test_get_data_on_points_currents(tmp_path):
    model = _write_model(tmp_path)
    dfs = model.get_data_on_points(
        x=[3.3, -0.5], y=[0.2, 1.0], crs=4326, format="df", quantity="u"
    )
    for df in dfs:
        assert df.loc["M2", "amplitude"] == pytest.approx(0.4, rel=1e-5)
        assert df.loc["M2", "phase"] == pytest.approx(100.0, rel=1e-5)
        assert df.loc["S2", "amplitude"] == pytest.approx(0.2, rel=1e-5)


def test_read_box_across_meridian(tmp_path):
    model = _write_model(tmp_path)
    ds = read_box(model, [-2.0, 2.0], [0.0, 1.0], constituents=["m2"], quantity="v")
    np.testing.assert_allclose(ds.lon.values, np.arange(-2.0, 2.0625, 0.125))
    np.testing.assert_allclose(ds.amplitude.values, 0.3, rtol=1e-6)


def test_predict_at_point_current(tmp_path):
    model = _write_model(tmp_path)
    t0 = datetime.datetime(2020, 1, 1)
    t1 = datetime.datetime(2020, 1, 2)
    u = predict_at_point(model, 3.0, 0.0, t0, t1, 30.0, quantity="u")
    assert u.name == "U"
    # |u| cannot exceed the sum of the amplitudes, times the nodal factors (< 1.1)
    assert 0.3 < np.abs(u).max() < 1.1 * 0.6
    with pytest.raises(ValueError, match="offset"):
        predict_at_point(model, 3.0, 0.0, t0, t1, 30.0, offset=1.0, quantity="u")


def test_export_map_current(tmp_path):
    model = _write_model(tmp_path / "model")
    filename = str(tmp_path / "u.nc")
    export_map(filename, model, [2.0, 4.0], [-1.0, 1.0], quantity="u")
    with xr.open_dataset(filename) as ds:
        assert ds.amplitude.attrs["units"] == "m s-1"
        assert "eastward velocity" in ds.amplitude.attrs["long_name"]
        np.testing.assert_allclose(
            ds.amplitude.sel(constituent="M2").values, 0.4, rtol=1e-6
        )


def test_read_box_across_meridian(tmp_path):
    """A box crossing 0 E is read in one go, with continuous longitudes and gaps as NaN."""
    os.makedirs(tmp_path, exist_ok=True)
    with open(os.path.join(tmp_path, "metadata.tml"), "w") as f:
        f.write('longname = "synthetic FES"\nformat = "fes2014"\n')
    # Amplitude varies with longitude, so the order of the two halves is checked
    amp = np.broadcast_to(LON, (LAT.size, LON.size)).astype("f4").copy()
    amp[:, LON == 0.5] = np.nan  # land
    ds = xr.Dataset(
        {
            "amplitude": (("lat", "lon"), amp),
            "phase": (("lat", "lon"), np.full(amp.shape, 10.0, "f4")),
        },
        coords={"lat": LAT, "lon": LON},
    )
    ds.to_netcdf(os.path.join(tmp_path, "m2.nc"))
    model = TideModelFes2014("synthetic", str(tmp_path))

    box = read_box(model, [-1.0, 1.0], [-1.0, 1.0])
    np.testing.assert_allclose(box.lon.values, np.arange(-1.0, 1.0625, 0.125))
    expected = np.mod(box.lon.values, 360.0) / 100.0
    expected[box.lon.values == 0.5] = np.nan
    np.testing.assert_allclose(box.amplitude.values[0, 0], expected, rtol=1e-6)
    np.testing.assert_allclose(box.phase.values[0], 10.0)

    # A box ending at 360 does not wrap around to 0
    box = model.get_data([359.0, 360.0], [-1.0, 1.0])
    assert box.lon.values.max() == 359.875
