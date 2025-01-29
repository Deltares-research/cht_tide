import matplotlib.pyplot as plt
import pandas as pd

from cht_tide import TideStationsDatabase, predict


def test_tide_stations():
    database = TideStationsDatabase(
        path="c:/work/projects/delftdashboard/delftdashboard_python/data/tide_stations"
    )

    dataset = database.dataset["xtide_free"]
    dataset.read_data()
    _gdf = dataset.gdf()

    station_name = dataset.station[0]["name"]

    _prd2 = dataset.predict(
        name=station_name, start="2023-01-01", end="2023-01-02", dt=300, format="df"
    )

    df = dataset.get_components(name=station_name)
    # Set times (pandas date range)
    times = pd.date_range(start="2023-01-01", end="2023-01-02", freq="10T")
    prd = predict(df, times, format="df")
    # plot the time series
    prd.plot()
    # Set the title to station name
    plt.title(station_name)
    plt.show()
