# Coastal Hazards Toolkit -Tides
CHT Tide is a Python package for fitting tidal harmonic constituents to observed water levels and predicting water levels from known constituents. It also provides access to gridded tide models and station databases.

## Installation

Install the latest release from PyPI:

```bash
python -m pip install cht-tide
```

Once the package is available on conda-forge, it can also be installed with:

```bash
conda install -c conda-forge cht_tide
```

The package does not bundle large tide-model or station datasets. Those data must be provided separately, either locally or through a configured S3 database.

## Quick example

Predict water levels from constituent amplitudes (metres) and phases (degrees):

```python
import pandas as pd

from cht_tide import predict

constituents = pd.DataFrame(
    {
        "amplitude": [0.85, 0.22, 0.18, 0.15, 0.12],
        "phase": [120.0, 145.0, 100.0, 30.0, 350.0],
    },
    index=["M2", "S2", "N2", "K1", "O1"],
)

times = pd.date_range("2024-01-01", periods=24, freq="h")
water_levels = predict(constituents, times)
```

See the [getting started guide](docs/getting_started.rst) and
[user guide](docs/user_guide/index.rst) for more examples.
