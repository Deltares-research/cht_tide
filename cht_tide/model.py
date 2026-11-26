"""Base tide model class.

Defines :class:`TideModel`, the abstract base for all concrete tidal dataset
implementations (e.g. FES2014, TPXO).  Handles metadata loading, optional
S3 file download, and interpolation of tidal constituents onto arbitrary
point sets.
"""

import os

import boto3
import geopandas as gpd
import numpy as np
import pandas as pd
import toml
import xarray as xr
from botocore import UNSIGNED
from botocore.client import Config
from pyproj import CRS
from shapely.geometry import Point

# Quantities a tide model can provide: water level (m), eastward and northward
# depth-averaged velocity (m/s)
QUANTITIES = {
    "z": "water level",
    "u": "eastward velocity",
    "v": "northward velocity",
}


class TideModel:
    """Abstract base class for a tidal model dataset.

    Subclasses must implement :meth:`get_data` and call
    :meth:`read_metadata` during initialisation.

    Attributes
    ----------
    database : object or None
        Parent :class:`~cht_tide.database.TideModelDatabase` instance.
    name : str
        Short identifier for this dataset.
    long_name : str
        Human-readable label.
    path : str
        Directory containing dataset files.
    main_constituents : list of str
        Names of the eight principal tidal constituents.
    files : list of str
        File names that must exist locally (used for S3 download checks).
    has_currents : bool
        True if the dataset also provides tidal currents (quantities ``"u"``
        and ``"v"``).
    """

    def __init__(self) -> None:
        self.database = None
        self.name = ""
        self.long_name = ""
        self.path = ""
        self.main_constituents = ["M2", "S2", "N2", "K2", "K1", "O1", "P1", "Q1"]
        self.files = []
        self.has_currents = False

    def quantity_folder(self, quantity: str = "z") -> str:
        """Sub folder (relative to ``self.path``) holding the files of *quantity*.

        The base implementation keeps all files in ``self.path``.
        """
        return ""

    def read_metadata(self) -> None:
        """Read dataset metadata from ``metadata.tml`` in ``self.path``.

        Sets attributes for every key found in the TOML file.  Also handles
        the legacy ``longname`` key and ensures ``self.long_name`` is always
        populated.
        """
        tml_file = os.path.join(self.path, "metadata.tml")
        tml = toml.load(tml_file)
        for key in tml:
            setattr(self, key, tml[key])
        # Long name for backwards compatibility
        if "longname" in tml:
            self.long_name = tml["longname"]
        # Make sure there is always a long_name
        if self.long_name == "":
            self.long_name = self.name

        self.crs = CRS(4326)

    def download(self, quantity: str = "z") -> None:
        """Download any missing dataset files of *quantity* from S3.

        Does nothing if ``self.s3_bucket`` is ``None`` or all files are
        already present locally. The files of a quantity are ``self.files`` in
        :meth:`quantity_folder` (locally and in the bucket).

        Parameters
        ----------
        quantity : str, optional
            ``"z"`` (water level, default), ``"u"`` or ``"v"`` (currents).
        """
        if getattr(self, "s3_bucket", None) is None:
            return
        folder = self.quantity_folder(quantity)
        local_files = [
            (file, os.path.join(self.path, folder, file)) for file in self.files
        ]
        missing = [(f, p) for f, p in local_files if not os.path.exists(p)]
        if not missing:
            return
        s3_client = boto3.client(
            "s3",
            endpoint_url=getattr(self, "s3_endpoint", None) or None,
            config=Config(signature_version=UNSIGNED),
        )
        os.makedirs(os.path.join(self.path, folder), exist_ok=True)
        key_prefix = f"{self.s3_key}/{folder}/" if folder else f"{self.s3_key}/"
        for file, local_path in missing:
            print(
                f"Downloading {folder + '/' if folder else ''}{file} from tide model {self.name} ..."
            )
            s3_client.download_file(self.s3_bucket, key_prefix + file, local_path)

    def get_data_on_points(
        self,
        gdf: gpd.GeoDataFrame = None,
        x=None,
        y=None,
        crs=None,
        format: str = "gdf",
        constituents="all",
        quantity: str = "z",
    ):
        """Interpolate tidal constituents onto a set of geographic points.

        Provide either *gdf* **or** *x*/*y*/*crs*.

        Parameters
        ----------
        gdf : gpd.GeoDataFrame, optional
            Points at which to extract tidal data.
        x : array-like, optional
            X (longitude) coordinates of points.
        y : array-like, optional
            Y (latitude) coordinates of points.
        crs : any, optional
            Coordinate reference system for *x*/*y* (passed to GeoPandas).
        format : str, optional
            Output format: ``"gdf"`` / ``"geodataframe"`` (default) or
            ``"dataframe"`` / ``"df"`` / ``"pandas"``.
        constituents : str or list of str, optional
            Which constituents to extract (``"all"`` or ``"main"``).
        quantity : str, optional
            ``"z"`` (water level in m, default), ``"u"`` (eastward velocity in
            m/s) or ``"v"`` (northward velocity in m/s). Predicting with the
            constituents of ``"u"`` and ``"v"`` gives the velocity components.

        Returns
        -------
        gpd.GeoDataFrame or list of pd.DataFrame
            When *format* is ``"gdf"``, the input GeoDataFrame with an
            ``"astro"`` column containing per-station DataFrames.
            When *format* is ``"dataframe"``, a list of DataFrames.
        """
        if quantity not in QUANTITIES:
            raise ValueError(
                f"Unknown quantity '{quantity}'; use one of {list(QUANTITIES)}"
            )
        if quantity != "z" and not self.has_currents:
            raise ValueError(f"Tide model {self.name} has no tidal currents.")

        # Download files if needed
        self.download(quantity)

        # The constituent list is built from the files on disk when the model
        # is loaded; refresh it if the files were only just downloaded.
        if not getattr(self, "constituents", None) and hasattr(
            self, "get_constituents"
        ):
            self.get_constituents()

        if constituents == "all":
            constituents = self.constituents
        elif constituents == "main":
            constituents = self.main_constituents

        if gdf is None:
            gdf = pd.DataFrame()
            gdf["geometry"] = [Point(x, y) for x, y in zip(x, y)]
            gdf = gpd.GeoDataFrame(gdf, crs=crs)

        gdf4326 = gdf.to_crs("EPSG:4326")
        xl = [gdf4326.geometry.x.min(), gdf4326.geometry.x.max()]
        yl = [gdf4326.geometry.y.min(), gdf4326.geometry.y.max()]
        xl[0] -= 0.25
        xl[1] += 0.25
        yl[0] -= 0.25
        yl[1] += 0.25

        # The longitudes of the box are continuous, also across the 0 meridian
        from cht_tide.export import read_box

        ds = read_box(self, xl, yl, constituents=constituents, quantity=quantity)
        lon0 = float(ds.lon.values[0])

        # Interpolate the vector components, so that phases are not averaged
        # across the 0/360 degree jump
        ds["tvu"] = ds.amplitude * np.cos(ds.phase * np.pi / 180.0)
        ds["tvv"] = ds.amplitude * np.sin(ds.phase * np.pi / 180.0)

        # Interpolate all points at once (pointwise, along a "point" dimension)
        xp = np.mod(gdf4326.geometry.x.to_numpy() - lon0, 360.0) + lon0
        yp = gdf4326.geometry.y.to_numpy()
        dsp = ds[["tvu", "tvv"]].interp(
            lon=xr.DataArray(xp, dims="point"), lat=xr.DataArray(yp, dims="point")
        )
        tvu = dsp.tvu.transpose("point", "constituent").to_numpy()
        tvv = dsp.tvv.transpose("point", "constituent").to_numpy()
        amplitude = np.sqrt(tvu**2 + tvv**2)
        phase = np.mod(np.arctan2(tvv, tvu) * 180.0 / np.pi, 360.0)

        # One DataFrame (indexed by constituent) per point
        dfs = []
        for ip in range(len(xp)):
            df = pd.DataFrame()
            df["constituent"] = constituents
            df["amplitude"] = amplitude[ip]
            df["phase"] = phase[ip]
            dfs.append(df.set_index("constituent"))

        if format == "gdf" or format == "geodataframe":
            if "astro" not in gdf.columns:
                gdf["astro"] = None
            for i, df in zip(gdf.index, dfs):
                gdf.at[i, "astro"] = df  # noqa: PD008
            return gdf
        elif format == "dataframe" or format == "df" or format == "pandas":
            return dfs

    def add_offset(self, data, offset: float = 0):
        """Add a constant vertical offset (datum correction) to tidal data.

        If the ``A0`` constituent is already present in the DataFrame its
        amplitude is incremented; otherwise a new row is appended.

        Parameters
        ----------
        data : gpd.GeoDataFrame or list of pd.DataFrame
            Tidal data as returned by :meth:`get_data_on_points`.
        offset : float, optional
            Vertical offset in metres (default ``0``).

        Returns
        -------
        gpd.GeoDataFrame or list of pd.DataFrame
            Updated tidal data with the offset applied.
        """

        def _add_or_update(df: pd.DataFrame) -> pd.DataFrame:
            if "A0" in df.index:
                df.loc["A0", "amplitude"] += offset
            else:
                new_row = pd.DataFrame(
                    {"amplitude": [offset], "phase": [0]}, index=["A0"]
                )
                df = pd.concat([df, new_row])
            return df

        if isinstance(data, gpd.GeoDataFrame):
            for i in data.index:
                if isinstance(data.at[i, "astro"], pd.DataFrame):
                    data.at[i, "astro"] = _add_or_update(data.at[i, "astro"])
            return data

        elif isinstance(data, list):
            return [_add_or_update(df) for df in data]
