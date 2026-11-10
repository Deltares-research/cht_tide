"""Tests for cht_tide.export against golden files of the MATLAB Delft Dashboard."""

import datetime
import os

import numpy as np
import pandas as pd
import xarray as xr

from cht_tide.export import (
    export_map,
    get_map,
    predict_at_point,
    read_box,
    write_tekal_timeseries,
)
from cht_tide.model import TideModel

DATA = os.path.join(os.path.dirname(__file__), "data", "export")


class _SyntheticModel(TideModel):
    """A global tide model on a 1 degree grid (longitudes 0 to 359), M2 and S2."""

    def __init__(self):
        super().__init__()
        self.name = "synthetic"
        self.s3_bucket = None
        self.constituents = ["M2", "S2"]
        lon = np.arange(0.0, 360.0)
        lat = np.arange(-80.0, 81.0)
        xx, yy = np.meshgrid(lon, lat)
        self.ds = xr.Dataset(
            {
                "amplitude": (
                    ("constituent", "lat", "lon"),
                    np.array([1.0 + 0.0 * xx, 0.5 + 0.0 * xx]),
                ),
                "phase": (
                    ("constituent", "lat", "lon"),
                    np.array([np.mod(xx, 360.0), 0.0 * xx + 90.0]),
                ),
            },
            coords={"constituent": self.constituents, "lon": lon, "lat": lat},
        )

    def get_data(self, xl, yl, constituents="all"):
        if xl[0] < 0.0 and xl[1] < 0.0:
            xl = [xl[0] + 360.0, xl[1] + 360.0]
        return self.ds.sel(lon=slice(xl[0], xl[1]), lat=slice(yl[0], yl[1]))


def test_tekal_timeseries_matches_matlab(tmp_path):
    times = pd.date_range("2020-01-01", periods=6, freq="h")
    series = pd.Series([1.2345, -0.5, 0, 12.25, -10.125, np.nan], index=times)
    filename = tmp_path / "point.tek"
    write_tekal_timeseries(str(filename), series, "10.500_50.250")
    with open(os.path.join(DATA, "point.tek"), "rb") as f:
        expected = f.read()
    assert filename.read_bytes() == expected


def test_box_across_zero_meridian():
    ds = read_box(_SyntheticModel(), [-5.0, 5.0], [10.0, 12.0])
    assert ds.lon.values[0] == -5.0 and ds.lon.values[-1] == 5.0
    assert np.all(np.diff(ds.lon.values) == 1.0)
    # Phase of M2 is the longitude (0 to 360) of the model
    assert ds.phase.sel(constituent="M2", lon=-3.0).values[0] == 357.0


def test_projected_map_interpolates_vectors():
    # UTM zone 31N around 3 degrees east; M2 phase passes 0/360 at 0 degrees east
    x, y, names, amp, phi = get_map(
        _SyntheticModel(), [100000.0, 300000.0], [5500000.0, 5600000.0], crs=32631
    )
    assert names == ["M2", "S2"]
    assert x.shape == (11, 21) and x[0, 1] - x[0, 0] == 10000.0
    assert np.allclose(amp[0], 1.0, atol=1e-3) and np.allclose(phi[1], 90.0)
    # Near the 0 meridian the phases stay close to 0/360, never near 180
    assert np.all(np.minimum(phi[0], 360.0 - phi[0]) < 5.0)


def test_export_map(tmp_path):
    export_map(str(tmp_path / "map.nc"), _SyntheticModel(), [4.0, 6.0], [50.0, 52.0])
    ds = xr.open_dataset(tmp_path / "map.nc")
    assert ds.amplitude.shape == (2, 3, 3) and list(ds.constituent.values) == [
        "M2",
        "S2",
    ]
    ds.close()


def test_predict_at_point():
    m = _SyntheticModel()
    t0 = datetime.datetime(2020, 1, 1)
    t1 = t0 + datetime.timedelta(days=2)
    wl = predict_at_point(m, -0.5, 10.0, t0, t1, 30.0, offset=1.0)
    assert len(wl) == 97 and wl.index[0] == t0
    assert abs(wl.mean() - 1.0) < 0.1 and wl.max() < 2.6 and wl.max() > 2.0
    # Local time is 2 hours ahead: the same water level two hours later
    wl2 = predict_at_point(m, -0.5, 10.0, t0, t1, 30.0, time_zone=2.0)
    assert np.allclose(wl2.values[4:], wl.values[:-4] - 1.0, atol=1e-4)


def test_points_across_zero_meridian():
    m = _SyntheticModel()
    dfs = m.get_data_on_points(x=[-3.0, 2.0], y=[10.0, 11.0], crs=4326, format="df")
    # M2 phase is the longitude (0 to 360) of the model
    assert np.isclose(dfs[0].loc["M2", "phase"], 357.0)
    assert np.isclose(dfs[1].loc["M2", "phase"], 2.0)


def test_land_mask():
    x, y, _, amp, phi = get_map(
        _SyntheticModel(), [4.0, 6.0], [50.0, 52.0], land_mask=lambda x, y: x > 5.0
    )
    assert (
        np.isnan(amp[:, :, x[0] > 5.0]).all()
        and np.isfinite(amp[:, :, x[0] <= 5.0]).all()
    )
    assert np.isnan(phi[:, :, x[0] > 5.0]).all()
