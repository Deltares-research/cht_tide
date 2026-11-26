Getting started
===============

CHT Tide fits tidal harmonic constituents to observed water levels and predicts
water levels from known constituent amplitudes and phases. It also provides
access to gridded tide models and station databases.

Installation
------------

Install the latest release from PyPI:

.. code-block:: bash

   python -m pip install cht-tide

Once the package is available on conda-forge, install it with:

.. code-block:: bash

   conda install -c conda-forge cht_tide

CHT Tide requires Python 3.10 or later. Installation provides the Python
package, but does not include the large tide-model or tide-station datasets.
These must be available locally or through a configured S3 database.

For development:

.. code-block:: bash

   git clone https://github.com/Deltares-research/cht_tide.git
   cd cht_tide
   pip install -e ".[tests]"

Predict tides from constituents
-------------------------------

The :func:`~cht_tide.tide_predict.predict` function accepts a
:class:`pandas.DataFrame` indexed by constituent name. Provide ``amplitude``
in metres and ``phase`` in degrees:

.. code-block:: python

   import pandas as pd
   from cht_tide import predict

   # Time axis: 7 days at 10-minute intervals
   times = pd.date_range("2024-01-01", periods=7 * 144, freq="10min")

   # Define a few constituents (amplitude in metres, phase in degrees)
   constituents = pd.DataFrame(
       {
           "amplitude": [0.85, 0.22, 0.18, 0.15, 0.12],
           "phase": [120.0, 145.0, 100.0, 30.0, 350.0],
       },
       index=["M2", "S2", "N2", "K1", "O1"],
   )

   # Predict water levels
   wl = predict(constituents, times)

   print(f"Max water level: {wl.max():.2f} m")
   print(f"Min water level: {wl.min():.2f} m")

The returned NumPy array contains predicted water levels in metres, in the same
order as the requested times.

Fit constituents to observations
--------------------------------

Use :meth:`~cht_tide.tide.Tide.decompose` to fit harmonic constituents to an
observed water-level time series. The example expects a CSV with ``time`` and
``water_level`` columns; adjust those names to match your data.

.. code-block:: python

   import pandas as pd

   from cht_tide.tide import Tide

   observations = pd.read_csv("water_levels.csv", parse_dates=["time"])
   times = observations["time"].dt.to_pydatetime()
   fit = Tide.decompose(
       heights=observations["water_level"].to_numpy(),
       t=times,
   )

   for row in fit.model:
       constituent = row["constituent"]
       print(
           f"{constituent.name:>4s}  "
           f"amplitude={row['amplitude']:.3f} m  "
           f"phase={row['phase']:.1f} deg"
       )

The default fit considers the NOAA constituent set and only includes
constituents with at least two complete cycles in the observation period. Use a
long enough, consistently sampled record for the constituents you want to
resolve.

Next steps
----------

* Read the :doc:`user guide <user_guide/index>` for model and station workflows.
* Browse the :doc:`API reference <api/index>` for class and function details.
