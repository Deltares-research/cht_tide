"""Export of tide model data: co-tidal maps and predicted time series at a point.

Port of the Export tab of the MATLAB Delft Dashboard Tide Database toolbox
(``ddb_TideDatabaseToolbox_export``, ``exportTEK``). Maps are exported to NetCDF. Maps are
read from a :class:`~cht_tide.model.TideModel` in a box and, for a projected coordinate
system, interpolated onto a regular grid in that system.
"""

import datetime
from typing import Any, Callable, List, Optional, Tuple

import numpy as np
import pandas as pd
import xarray as xr
from pyproj import CRS, Transformer

from cht_tide.tide_predict import predict

# Spacing (m) of the grid onto which maps are interpolated in a projected system
PROJECTED_SPACING = 10000.0


def read_box(
    model: Any, xl: List[float], yl: List[float], constituents: Any = "all"
) -> xr.Dataset:
    """Read amplitudes and phases of a tide model in a geographic box.

    Parameters
    ----------
    model : TideModel
        The tide model.
    xl, yl : list of float
        Longitude and latitude limits.
    constituents : str or list of str, optional
        Constituents to read (``"all"`` by default).

    Returns
    -------
    xr.Dataset
        ``amplitude`` (m) and ``phase`` (degrees) with dimensions ``constituent``,
        ``lat``, ``lon``; the longitudes are continuous over the box, also when it crosses
        the 0 meridian.
    """
    model.download()
    if not getattr(model, "constituents", None) and hasattr(model, "get_constituents"):
        model.get_constituents()
    x0, x1 = float(xl[0]), float(xl[1])
    shift = 360.0 * np.floor(x0 / 360.0)
    x0, x1 = x0 - shift, x1 - shift
    if x1 <= 360.0:
        ds = model.get_data([x0, x1], yl, constituents=constituents)
    else:
        # The box crosses the 0 meridian of the model (longitudes 0 to 360)
        ds = xr.concat(
            [
                model.get_data([x0, 360.0], yl, constituents=constituents),
                model.get_data(
                    [0.0, x1 - 360.0], yl, constituents=constituents
                ).assign_coords(lon=lambda d: d.lon + 360.0),
            ],
            dim="lon",
        )
    return ds.assign_coords(lon=ds.lon + shift)


def get_map(
    model: Any,
    xl: List[float],
    yl: List[float],
    crs: Any = 4326,
    constituents: Any = "all",
    spacing: float = PROJECTED_SPACING,
    land_mask: Optional[Callable[[np.ndarray, np.ndarray], np.ndarray]] = None,
) -> Tuple[np.ndarray, np.ndarray, List[str], np.ndarray, np.ndarray]:
    """Amplitude and phase maps of a tide model in a box.

    ``land_mask(x, y)``, if given, returns True for the grid points (in ``crs``) that are
    land; amplitude and phase are NaN there. This removes the values that a tide model such
    as FES2014 (extrapolated) has extrapolated onto land. See :func:`_get_map` for the other
    parameters.
    """
    x, y, names, amplitude, phase = _get_map(model, xl, yl, crs, constituents, spacing)
    if land_mask is not None:
        land = np.asarray(land_mask(x, y), dtype=bool)
        amplitude = np.where(land[None, :, :], np.nan, amplitude)
        phase = np.where(land[None, :, :], np.nan, phase)
    return x, y, names, amplitude, phase


def _get_map(
    model: Any,
    xl: List[float],
    yl: List[float],
    crs: Any = 4326,
    constituents: Any = "all",
    spacing: float = PROJECTED_SPACING,
) -> Tuple[np.ndarray, np.ndarray, List[str], np.ndarray, np.ndarray]:
    """Amplitude and phase maps of a tide model in a box.

    Parameters
    ----------
    model : TideModel
        The tide model.
    xl, yl : list of float
        Box limits in ``crs``.
    crs : optional
        Coordinate reference system of the box (default WGS 84).
    constituents : str or list of str, optional
        Constituents (``"all"`` by default).
    spacing : float, optional
        Grid spacing (m) for a projected system.

    Returns
    -------
    x, y : np.ndarray
        Grid coordinates in ``crs``, shape ``(ny, nx)``.
    constituents : list of str
        Constituent names.
    amplitude, phase : np.ndarray
        Shape ``(nconst, ny, nx)``; NaN on land.

    Notes
    -----
    In a geographic system the grid of the tide model is used. In a projected system the
    maps are interpolated onto a grid with the given spacing, read from the tide model in
    the geographic box around it plus one degree. Fix: MATLAB interpolated the phases
    directly, which went wrong across the 0/360 degree jump; the vector components are
    interpolated instead.
    """
    crs = CRS(crs)
    if crs.is_geographic:
        ds = read_box(model, xl, yl, constituents)
        x, y = np.meshgrid(ds.lon.values, ds.lat.values)
        return (
            x,
            y,
            [str(c) for c in ds.constituent.values],
            ds.amplitude.values,
            np.mod(ds.phase.values, 360.0),
        )

    to_wgs84 = Transformer.from_crs(crs, 4326, always_xy=True).transform
    xb, yb = np.meshgrid(np.linspace(xl[0], xl[1], 11), np.linspace(yl[0], yl[1], 11))
    lon, lat = to_wgs84(xb, yb)
    ds = read_box(
        model,
        [lon.min() - 1.0, lon.max() + 1.0],
        [lat.min() - 1.0, lat.max() + 1.0],
        constituents,
    )
    x, y = np.meshgrid(
        np.arange(xl[0], xl[1] + 0.5 * spacing, spacing),
        np.arange(yl[0], yl[1] + 0.5 * spacing, spacing),
    )
    lon, lat = to_wgs84(x, y)
    pts = {
        "lon": xr.DataArray(lon.ravel(), dims="points"),
        "lat": xr.DataArray(lat.ravel(), dims="points"),
    }
    rad = np.pi / 180.0
    u = (ds.amplitude * np.cos(ds.phase * rad)).interp(**pts).values
    v = (ds.amplitude * np.sin(ds.phase * rad)).interp(**pts).values
    shape = (len(ds.constituent),) + x.shape
    amplitude = np.hypot(u, v).reshape(shape)
    phase = np.mod(np.arctan2(v, u) / rad, 360.0).reshape(shape)
    return x, y, [str(c) for c in ds.constituent.values], amplitude, phase


def write_netcdf_map(
    filename: str,
    x: np.ndarray,
    y: np.ndarray,
    constituents: List[str],
    amplitude: np.ndarray,
    phase: np.ndarray,
    crs: Any = 4326,
) -> None:
    """Write amplitude and phase maps to a CF-compliant NetCDF file.

    Dimensions are ``constituent``, ``lat``, ``lon`` (or ``y``, ``x`` in a projected
    system); the coordinate reference system is given by the grid mapping variable ``crs``.
    """
    crs = CRS(crs)
    if crs.is_geographic:
        xname, yname = "lon", "lat"
        xattrs = {
            "standard_name": "longitude",
            "long_name": "longitude",
            "units": "degrees_east",
            "axis": "X",
        }
        yattrs = {
            "standard_name": "latitude",
            "long_name": "latitude",
            "units": "degrees_north",
            "axis": "Y",
        }
    else:
        xname, yname = "x", "y"
        xattrs = {
            "standard_name": "projection_x_coordinate",
            "long_name": "x coordinate",
            "units": "m",
            "axis": "X",
        }
        yattrs = {
            "standard_name": "projection_y_coordinate",
            "long_name": "y coordinate",
            "units": "m",
            "axis": "Y",
        }
    grid_mapping = crs.to_cf()
    grid_mapping["crs_wkt"] = crs.to_wkt()
    if crs.to_epsg():
        grid_mapping["epsg_code"] = f"EPSG:{crs.to_epsg()}"
    dims = ("constituent", yname, xname)
    ds = xr.Dataset(
        {
            "amplitude": (
                dims,
                amplitude.astype("float32"),
                {
                    "long_name": "tidal amplitude of the water level",
                    "units": "m",
                    "grid_mapping": "crs",
                },
            ),
            "phase": (
                dims,
                phase.astype("float32"),
                {
                    "long_name": "tidal phase of the water level (relative to Greenwich)",
                    "units": "degrees",
                    "grid_mapping": "crs",
                },
            ),
            "crs": ((), np.int32(0), grid_mapping),
        },
        coords={
            "constituent": (
                "constituent",
                constituents,
                {"long_name": "tidal constituent"},
            ),
            xname: (xname, np.asarray(x[0, :], dtype=float), xattrs),
            yname: (yname, np.asarray(y[:, 0], dtype=float), yattrs),
        },
        attrs={"Conventions": "CF-1.8"},
    )
    encoding = {name: {"_FillValue": None} for name in (xname, yname, "crs")}
    encoding["amplitude"] = {"_FillValue": np.float32(-999.0)}
    encoding["phase"] = {"_FillValue": np.float32(-999.0)}
    ds.to_netcdf(filename, encoding=encoding)


def export_map(
    filename: str,
    model: Any,
    xl: List[float],
    yl: List[float],
    crs: Any = 4326,
    land_mask: Optional[Callable[[np.ndarray, np.ndarray], np.ndarray]] = None,
) -> None:
    """Export the water-level amplitude and phase maps of all constituents in a box to NetCDF.

    Parameters
    ----------
    filename : str
        File to write.
    model : TideModel
        The tide model.
    xl, yl : list of float
        Box limits in ``crs``.
    crs : optional
        Coordinate reference system of the box and of the exported grid.
    land_mask : callable, optional
        Returns True for land points (see :func:`get_map`).

    Notes
    -----
    Only water levels: unlike the MATLAB version (TPXO), the tide models of cht_tide
    have no tidal currents. The MATLAB version wrote Tekal or mat files.
    """
    x, y, constituents, amplitude, phase = get_map(
        model, xl, yl, crs, land_mask=land_mask
    )
    write_netcdf_map(filename, x, y, constituents, amplitude, phase, crs)


def predict_at_point(
    model: Any,
    x: float,
    y: float,
    start: datetime.datetime,
    stop: datetime.datetime,
    dt: float,
    crs: Any = 4326,
    time_zone: float = 0.0,
    offset: float = 0.0,
) -> pd.Series:
    """Predicted water level of a tide model at a point.

    Parameters
    ----------
    model : TideModel
        The tide model.
    x, y : float
        The point, in ``crs``.
    start, stop : datetime.datetime
        Period, in the local time zone.
    dt : float
        Time step (minutes).
    crs : optional
        Coordinate reference system of the point.
    time_zone : float, optional
        Local time zone (hours ahead of UTC); the times of the series are local times.
    offset : float, optional
        Vertical offset (m), added to the series.

    Returns
    -------
    pd.Series
        Water level (m) indexed by local time.

    Notes
    -----
    Fix: the MATLAB version ignored the time zone and the vertical offset.
    """
    lon, lat = Transformer.from_crs(CRS(crs), 4326, always_xy=True).transform(x, y)
    ds = read_box(model, [lon - 1.0, lon + 1.0], [lat - 1.0, lat + 1.0])
    rad = np.pi / 180.0
    u = (ds.amplitude * np.cos(ds.phase * rad)).interp(lon=lon, lat=lat).values
    v = (ds.amplitude * np.sin(ds.phase * rad)).interp(lon=lon, lat=lat).values
    df = pd.DataFrame(
        {"amplitude": np.hypot(u, v), "phase": np.mod(np.arctan2(v, u) / rad, 360.0)},
        index=[str(c) for c in ds.constituent.values],
    )
    if not np.isfinite(df["amplitude"]).any():
        raise ValueError("The point is outside the tide model (on land?)")
    times = pd.date_range(start, stop, freq=pd.Timedelta(minutes=dt))
    utc = times - pd.Timedelta(hours=time_zone)
    wl = predict(df.dropna(), utc) + offset
    return pd.Series(wl, index=times, name="WL")


def write_tekal_timeseries(filename: str, series: pd.Series, block_name: str) -> None:
    """Write a water-level time series to a Tekal file (``exportTEK``)."""
    values = np.where(np.isnan(series.values), -999.0, series.values)
    strings = [f"{v:10.3f}".strip() for v in values]
    width = max(len(s) for s in strings) if strings else 0
    lines = ["* column 1 : Date", "* column 2 : Time", "* column 3 : WL", block_name]
    lines.append(f"{len(values)} 3")
    for t, s in zip(series.index, strings):
        lines.append(f"{t:%Y%m%d %H%M%S} {s.rjust(width)}")
    with open(filename, "w", newline="\n") as f:
        f.write("\n".join(lines) + "\n")


def point_name(x: float, y: float) -> str:
    """Name of a point as in the MATLAB version, e.g. ``10.500_50.250``."""
    return f"{x:0.3f}_{y:0.3f}"


def export_timeseries(
    filename: str, series: pd.Series, x: float, y: float, format: Optional[str] = None
) -> None:
    """Write a predicted time series to a Tekal (``.tek``) or csv file."""
    format = format or ("csv" if filename.lower().endswith(".csv") else "tek")
    if format == "csv":
        series.to_csv(filename, header=False)
    else:
        write_tekal_timeseries(filename, series, point_name(x, y))
