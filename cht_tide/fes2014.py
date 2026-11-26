"""FES2014 tidal model reader.

Implements :class:`TideModelFes2014`, a subclass of :class:`~cht_tide.model.TideModel`
that reads tidal amplitude and phase data from the FES2014 NetCDF files stored
one file per constituent.

Water levels are read from ``<path>/<constituent>.nc``; tidal currents, when
available, from ``<path>/eastward_velocity/<constituent>.nc`` (``Ua``, ``Ug``) and
``<path>/northward_velocity/<constituent>.nc`` (``Va``, ``Vg``).
"""

import os

import netCDF4
import numpy as np
import xarray as xr

from cht_tide.model import QUANTITIES, TideModel

# Sub folder, amplitude variable and phase variable of each quantity
_FES_QUANTITY = {
    "z": ("", "amplitude", "phase"),
    "u": ("eastward_velocity", "Ua", "Ug"),
    "v": ("northward_velocity", "Va", "Vg"),
}


class TideModelFes2014(TideModel):
    """FES2014 tidal model dataset.

    Reads constituent data from a directory of NetCDF files, each named
    ``<constituent>.nc``, containing ``amplitude`` (in cm) and ``phase``
    (in degrees) variables on a regular lon/lat grid. Tidal currents (in cm/s)
    are read from the ``eastward_velocity`` and ``northward_velocity`` sub
    folders, if they exist (or are listed as available in ``metadata.tml`` with
    ``currents = true``, in which case they are downloaded from S3).

    Parameters
    ----------
    name : str
        Short name identifying this dataset.
    path : str
        Directory where the FES2014 NetCDF files and ``metadata.tml`` are stored.
    """

    # get_data accepts a longitude box that runs past 360 (crosses the 0 meridian)
    reads_across_meridian = True

    def __init__(self, name: str, path: str) -> None:
        super().__init__()

        self.name = name
        self.path = path
        self.read_metadata()
        self.get_constituents()
        self.has_currents = bool(getattr(self, "currents", False)) or all(
            os.path.isdir(os.path.join(self.path, _FES_QUANTITY[q][0]))
            for q in ("u", "v")
        )

    def quantity_folder(self, quantity: str = "z") -> str:
        """Sub folder (relative to ``self.path``) holding the files of *quantity*."""
        return _FES_QUANTITY[quantity][0]

    def get_constituents(self) -> None:
        """Populate ``self.constituents`` from NetCDF file names in ``self.path``."""
        filenames = os.listdir(self.path)
        self.constituents = []
        for filename in filenames:
            if filename.endswith(".nc"):
                self.constituents.append(filename.split(".")[0].upper())

    def get_data(
        self, xl: list, yl: list, constituents: str = "all", quantity: str = "z"
    ) -> xr.Dataset:
        """Extract amplitude and phase data for a geographic bounding box.

        Parameters
        ----------
        xl : list of float
            Longitude bounds ``[lon_min, lon_max]`` in degrees east.
        yl : list of float
            Latitude bounds ``[lat_min, lat_max]`` in degrees north.
        constituents : str or list of str, optional
            Constituents to extract; ``"all"`` (default) returns all
            constituents found in the dataset.
        quantity : str, optional
            ``"z"`` (water level, default), ``"u"`` (eastward velocity) or
            ``"v"`` (northward velocity).

        Returns
        -------
        xr.Dataset
            Dataset with dimensions ``constituent``, ``lat``, ``lon`` and
            variables ``amplitude`` (metres, or m/s for currents) and ``phase``
            (degrees).

        Raises
        ------
        ValueError
            If *quantity* is unknown, or is a current while the dataset has none.
        """
        if quantity not in QUANTITIES:
            raise ValueError(
                f"Unknown quantity '{quantity}'; use one of {list(QUANTITIES)}"
            )
        if quantity != "z" and not self.has_currents:
            raise ValueError(f"Tide model {self.name} has no tidal currents.")
        folder, amp_name, phase_name = _FES_QUANTITY[quantity]
        path = os.path.join(self.path, folder)

        if isinstance(constituents, str) and constituents == "all":
            constituents = self.constituents

        if len(constituents) == 0:
            # Files were probably just downloaded from S3, so get the constituents
            self.get_constituents()
            constituents = self.constituents

        if len(constituents) == 0:
            raise FileNotFoundError(
                f"No constituent files (*.nc) found in {self.path} for tide model "
                f"{self.name}."
            )

        nconst = len(constituents)

        if xl[0] < 0.0 and xl[1] < 0.0:
            xl = [xl[0] + 360.0, xl[1] + 360.0]

        # The files are read with netCDF4 rather than xarray: opening a file with
        # xarray costs about 0.25 s, against milliseconds for netCDF4, and a box
        # reads all ~34 constituent files (once per quantity).
        filename = os.path.join(path, f"{constituents[0]}.nc")
        with netCDF4.Dataset(filename) as data:
            lon_all = np.asarray(data["lon"][:], dtype=float)
            lat_all = np.asarray(data["lat"][:], dtype=float)
        # Latitudes and longitudes in the box, both limits included (as
        # xarray's sel(slice) did). A box crossing the 360 (= 0) meridian is
        # read as two longitude slices from the same file.
        ilat = np.flatnonzero((lat_all >= yl[0]) & (lat_all <= yl[1]))
        lat_slice = slice(ilat[0], ilat[-1] + 1) if ilat.size else slice(0, 0)
        lon_slices = []
        lon_parts = []
        ranges = [(xl[0], xl[1], 0.0)]
        if xl[1] > 360.0:
            ranges.append((xl[0] - 360.0, xl[1] - 360.0, 360.0))
        for x0, x1, offset in ranges:
            j = np.flatnonzero((lon_all >= x0) & (lon_all <= x1))
            if j.size:
                lon_slices.append(slice(j[0], j[-1] + 1))
                lon_parts.append(lon_all[j[0] : j[-1] + 1] + offset)
        lon = np.concatenate(lon_parts) if lon_parts else np.zeros(0)
        lat = lat_all[lat_slice]

        amplitude = np.full((nconst, lat.size, lon.size), np.nan)
        phase = np.full((nconst, lat.size, lon.size), np.nan)
        if lat.size and lon.size:
            for ic, constituent in enumerate(constituents):
                filename = os.path.join(path, f"{constituent}.nc")
                with netCDF4.Dataset(filename) as data:
                    amplitude[ic] = np.hstack(
                        [_read(data[amp_name], lat_slice, s) for s in lon_slices]
                    )
                    phase[ic] = np.hstack(
                        [_read(data[phase_name], lat_slice, s) for s in lon_slices]
                    )
        # Convert amplitude from cm (cm/s) to metres (m/s)
        amplitude /= 100.0

        return xr.Dataset(
            data_vars={
                "amplitude": (("constituent", "lat", "lon"), amplitude),
                "phase": (("constituent", "lat", "lon"), phase),
            },
            coords={"constituent": list(constituents), "lat": lat, "lon": lon},
        )


def _read(variable, lat_slice: slice, lon_slice: slice) -> np.ndarray:
    """Read a lat/lon block of a netCDF variable as floats, fill values as NaN."""
    return np.ma.filled(
        np.ma.asarray(variable[lat_slice, lon_slice]).astype(float), np.nan
    )
