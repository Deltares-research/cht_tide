import datetime
from pathlib import Path

import pandas as pd

from cht_tide import TideStationsDatabase, predict


def test_tide_stations():
    # Arrange
    database = TideStationsDatabase(path=Path(__file__).parent / "tide_stations")
    dataset = database.dataset["xtide_free"]
    dataset.read_data()
    station_name = dataset.station[0]["name"]
    start = "2023-01-01"
    end = "2023-01-02"
    dt = datetime.timedelta(minutes=10)
    times = pd.date_range(start=start, end=end, freq=dt)

    # Act
    _prd2 = dataset.predict(
        name=station_name, start=start, end=end, dt=dt.total_seconds(), format="df"
    )
    df = dataset.get_components(name=station_name)
    prd = predict(df, times, format="df")

    # Assert
    assert len(times) == len(prd)
    assert len(times) == len(_prd2)
    assert prd.equals(_prd2)
