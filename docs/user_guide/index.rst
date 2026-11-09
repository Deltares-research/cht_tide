User guide
==========

Harmonic analysis
-----------------

The :class:`~cht_tide.tide.Tide` class performs harmonic analysis on a water
level time series, fitting amplitudes and phases for tidal constituents.

.. code-block:: python

   from cht_tide.tide import Tide

   fit = Tide.decompose(heights=wl_array, t=time_array)

   # Fitted constituents, amplitudes (metres), and phases (degrees)
   fit.model

The analysis uses a least-squares fit with nodal corrections computed from the
:mod:`cht_tide.nodal_corrections` and :mod:`cht_tide.astro` modules.

Tidal prediction
----------------

:func:`~cht_tide.tide_predict.predict` synthesises a water level time series
from constituent data in a pandas DataFrame indexed by constituent name, with
``amplitude`` in metres and ``phase`` in degrees:

.. code-block:: python

   from cht_tide.tide_predict import predict

   wl = predict(constituents, times)

The output is a NumPy array in the same order as ``times``. The function
applies astronomical arguments and nodal corrections automatically.

Global tide models
------------------

:class:`~cht_tide.model.TideModel` provides access to gridded global tide
models (currently FES2014). Use :class:`~cht_tide.database.TideModelDatabase`
to retrieve a model and interpolate constituent amplitudes and phases at
geographic coordinates:

.. code-block:: python

   from cht_tide.database import TideModelDatabase

   db = TideModelDatabase(path="/data/tide_models")
   model = db.get_dataset("fes2014_extrap")
   point_data = model.get_data_on_points(
       x=[4.0, 5.0],
       y=[52.0, 53.0],
       crs="EPSG:4326",
       format="dataframe",
       constituents="main",
   )

``point_data`` is a list of DataFrames, one for each point. The database also
provides ``db.dataset_names()`` to list the available models. Model files must
be available locally or configured for download from an S3 source; they are
distributed separately from the Python package.

Tide station databases
----------------------

:class:`~cht_tide.tide_stations.TideStationsDatabase` manages collections of
tide station datasets containing harmonic constituent information at discrete
station locations:

.. code-block:: python

   from cht_tide.tide_stations import TideStationsDatabase

   db = TideStationsDatabase(path="/data/tide_stations")
   dataset = db.dataset["xtide_free"]

   stations = dataset.get_gdf()
   station_name = stations.iloc[0]["name"]
   constituents = dataset.get_components(name=station_name)

``get_gdf`` returns station locations as a GeoDataFrame, and
``get_components`` returns a DataFrame of amplitudes and phases for the
selected station. Station datasets are distributed separately from the
Python package.
