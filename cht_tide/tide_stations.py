# -*- coding: utf-8 -*-
"""
Created on Sun Apr 25 10:58:08 2021

@author: Maarten van Ormondt
"""

import os
import numpy as np
import pandas as pd
import toml
import boto3
import xarray as xr
from botocore import UNSIGNED
from botocore.client import Config

import geopandas as gpd
import shapely

from .tide_predict import predict

class TideStationsDataset:
    def __init__(self, name, path):
        self.name = name
        self.long_name = name
        self.path = path
        self.gdf = gpd.GeoDataFrame()
        self.is_read = False
        self.read_metadata()

    def read_metadata(self):
        if not os.path.exists(os.path.join(self.path, "metadata.tml")):
            print("Warning! Tide stations metadata file not found: " + os.path.join(self.path, "metadata.tml"))
            return
        metadata = toml.load(os.path.join(self.path, "metadata.tml"))
        if "longname" in metadata:
            self.long_name = metadata["longname"]
        elif "long_name" in metadata:
            self.long_name = metadata["long_name"]
        self.file = metadata["file"]

    def read_data(self):
        """Reads the netcdf file and store it in self.data"""
        if self.is_read:
            return
        filename = os.path.join(self.path, self.file)
        if not os.path.exists(filename):
            print("Warning! Tide stations dataset file not found: " + filename)
            return
        # Read the netcdf file using xarray
        self.data = xr.open_dataset(filename)
        # Loop through stations
        nr_stations = len(self.data["lon"])
        self.station = []
        for i in range(nr_stations):
            station = {}
            # name
            name = "unknown"
            name_s1 = self.data["stations"][:,i].values
            # convert dtype='|S1' to string
            try:
                name = "".join([x.decode("utf-8") for x in name_s1]).strip()
            except:
                print("Error decoding name")           
            # id
            id_s1 = self.data["idcodes"][:,i].values
            # convert dtype='|S1' to string
            id = "".join([x.decode("utf-8") for x in id_s1]).strip()
            station["name"] = name
            station["id"] = id
            station["lon"] = self.data["lon"][i].values
            station["lat"] = self.data["lat"][i].values
            self.station.append(station)
        # Read the components
        nr_components = np.shape(self.data["components"])[1]
        self.components = []
        for i in range(nr_components):
            components_s1 = self.data["components"][:,i].values
            self.components.append("".join([x.decode("utf-8") for x in components_s1]).strip())

        self.data.close()

        self.is_read = True

    def find_index_by_name(self, name):
        if not self.is_read:
            self.read_data()
        for i, station in enumerate(self.station):
            if station["name"] == name:
                return i
        return None
    
    def find_index_by_id(self, id):
        if not self.is_read:
            self.read_data()
        for i, station in enumerate(self.station):
            if station["id"] == id:
                return i
        return None
    
    def get_components(self, name=None, id=None, index=None, sort=True):
        """Return Pandas dataframe with the tidal components for a station"""
        if name is not None:
            i = self.find_index_by_name(name)
        elif id is not None:
            i = self.find_index_by_id(id)
        else:
            print("Please provide either name or id.")
            return
        if i is None:
            print("Station not found.")
            return
        if not self.is_read:
            self.read_data()
        # Get the amplitudes
        amplitudes = self.data["amplitude"][:,i].values
        # Get the phases
        phases = self.data["phase"][:,i].values
        # Create a dataframe
        df = pd.DataFrame({"constituent": self.components, "amplitude": amplitudes, "phase": phases})
        df = df.set_index("constituent")
        if sort:
            # Sort by amplitude
            df = df.sort_values(by="amplitude", ascending=False)
            # Remove rows with amplitude = 0
            df = df[df.amplitude > 0.0]
        return df

    def predict(self, name=None, id=None, start=None, end=None, t=None, dt=None, offset=0.0, format="tek", filename=None):
        if name is not None:
            components = self.get_components(name=name)
        elif id is not None:
            components = self.get_components(id=id)
        else:
            print("Please provide either name or id.")
            return
        if start is not None and end is not None:
            # if start and end are strings, convert them to datetime objects
            if isinstance(start, str):
                start = pd.to_datetime(start)
            if isinstance(end, str):
                end = pd.to_datetime(end)
            if dt is None:
                dt = 600.0 # seconds
            times = pd.date_range(start=start, end=end, freq=f"{dt}s")
        elif t is not None:
            times = t
        else:
            print("Please provide either t0 and t1, or t.")
            return
        prd = predict(components, times, format="df")
        prd = prd + offset
        if filename is not None:
            if format == "tek":
                # Write to a .tek file
                df2tekaltimeseries(prd, filename)
            elif format == "csv":
                # Write to a .csv file, skipping the header
                prd.to_csv(filename, header=False)
        return prd
        
    def get_gdf(self):
        if not self.is_read:
            self.read_data()
        if len(self.gdf) == 0:    
            gdf_list = []
            # Loop through points
            for station in self.station:
                point = shapely.geometry.Point(station["lon"], station["lat"])
                d = {"id": station["id"], "name": station["name"], "geometry": point}
                gdf_list.append(d)
            self.gdf = gpd.GeoDataFrame(gdf_list, crs=4326)
        return self.gdf
    
    def station_names(self):
        """Return lists of station names and ids"""
        name_list = []
        id_list = []
        # Loop through the keys of the dictionary
        for station in self.station:
            name_list.append(station["name"])
            id_list.append(station["id"])
        return name_list, id_list

class TideStationsDatabase:
    """
    The main Tide Stations Database class
    
    :param pth: Path name where bathymetry tiles will be cached.
    :type pth: string            
    """
    
    def __init__(self, path=None,
                 s3_bucket=None,
                 s3_key=None,
                 s3_region=None):
        self.path    = path
        self.dataset = {}
        self.s3_client = None
        self.s3_bucket = s3_bucket
        self.s3_key = s3_key
        self.s3_region = s3_region
        self.read()
    
    def read(self):
        """
        Reads meta-data of all datasets in the database. 
        """
        if self.path is None:
            print("Path to tide stations database not set !")
            return
        
        # Check if the path exists. If not, create it.
        if not os.path.exists(self.path):
            os.makedirs(self.path)

        # Read in database
        tml_file = os.path.join(self.path, "tide_stations.tml")
        if not os.path.exists(tml_file):
            print("Warning! Tide stations database file not found: " + tml_file)
            return

        datasets = toml.load(tml_file)

        for d in datasets["dataset"]:

            name = d["name"]

            if "path" in d:
                path = d["path"]
            else:
                path = os.path.join(self.path, name)

            # # Read the meta data for this dataset
            # fname = os.path.join(path, "metadata.tml")

            # if os.path.exists(fname):
            #     metadata = toml.load(fname)
            #     dataset_format = metadata["format"]
            # else:
            #     print("Could not find metadata file for dataset " + name + " ! Skipping dataset.")
            #     continue
             
            self.dataset[name] = TideStationsDataset(name, path)

    def check_online_database(self):
        if self.s3_client is None:
            self.s3_client = boto3.client('s3', config=Config(signature_version=UNSIGNED))
        if self.s3_bucket is None:
            return
        # First download a copy of bathymetry.tml and call it bathymetry_s3.tml
        key = f"{self.s3_key}/tide_stations.tml"
        filename = os.path.join(self.path, "tide_stations_s3.tml")
        print("Updating tide stations database ...")
        try:
            self.s3_client.download_file(Bucket=self.s3_bucket,     # assign bucket name
                                         Key=key,           # key is the file name
                                         Filename=filename) # storage file path
        except:
            # Download failed
            print(f"Failed to download {key} from {self.s3_bucket}. Database will not be updated.")
            return

        # Read bathymetry_s3.tml
        short_name_list, long_name_list = self.dataset_names()
        datasets_s3 = toml.load(filename)
        tide_stations_added = False
        added_names = []
        # Loop through s3 datasets, and check whether they exist in the local database.
        # If so, check if the metadata also exists. If not, make local folder and download the metadata.
        # Additionally, check if available_tiles.nc in s3 and not in local database, download it.
        for d in datasets_s3["dataset"]:
            # Get list of existing datasets
            s3_name = d["name"]
            if s3_name not in short_name_list:
                # Dataset not in local database
                print(f"Adding tide stations {s3_name} to local database ...")
                # Create folder and download metadata
                path = os.path.join(self.path, s3_name)
                os.makedirs(path, exist_ok=True)
                key = f"{self.s3_key}/{s3_name}/metadata.tml"
                filename = os.path.join(path, "metadata.tml")
                # Download metadata
                try:
                    self.s3_client.download_file(Bucket=self.s3_bucket, # assign bucket name
                                                Key=key,               # key is the file name
                                                Filename=filename)     # storage file path
                except Exception as e:
                    print(e)
                    print(f"Failed to download {key}. Skipping tide stations dataset.")
                    continue
                # Necessary data has been downloaded    
                tide_stations_added = True
                added_names.append(s3_name)
        # Write new local bathymetry.tml
        if tide_stations_added:
            d = {}
            d["dataset"] = []
            for name in short_name_list:
                d["dataset"].append({"name": name})
            for name in added_names:
                d["dataset"].append({"name": name})
            # Now write the new bathymetry.tml
            with open(os.path.join(self.path, "tide_stations.tml"), "w") as tml:
                toml.dump(d, tml)            
            # Read the database again
            self.dataset = {}
            self.read()
        # else:
        #     print("No new tide models were added to the local database.")

    # def get_dataset(self, name):
    #     for dataset in self.dataset:
    #         if dataset.name == name:
    #             return dataset
    #     return None

    def dataset_names(self):
        short_name_list = []
        long_name_list = []
        # self.dataset is a dictionary
        # Loop through the keys of the dictionary
        for key in self.dataset.keys():
            short_name_list.append(key)
            long_name_list.append(self.dataset[key].long_name)
        # for dataset in self.dataset:
        #     short_name_list.append(dataset.name)
        #     long_name_list.append(dataset.long_name)
        return short_name_list, long_name_list


# def dict2yaml(file_name, dct, sort_keys=False):
#     yaml_string = yaml.dump(dct, sort_keys=sort_keys)    
#     file = open(file_name, "w")  
#     file.write(yaml_string)
#     file.close()

# def yaml2dict(file_name):
#     file = open(file_name,"r")
#     dct = yaml.load(file, Loader=yaml.FullLoader)
#     return dct

def df2tekaltimeseries(df, filename):
    """Write a Pandas dataframe to a .tek file"""
    nt = len(df)
    # Convert index of dataframe to string with format "YYYYMMDD HHMMSS"
    indexstr = df.index.strftime("%Y%m%d %H%M%S")
    with open(filename, "w") as f:
        f.write("* column 1 : Date\n")
        f.write("* column 2 : Time\n")
        f.write("* column 3 : WL\n")
        f.write("BL01\n")
        f.write(f"{nt} 4\n")
        j = 0
        for i, row in df.iterrows():
            # date, time and first column of data
            tstr = indexstr[j]
            j += 1
            vstr = f"{row[0]:7.3f}"
            f.write(f"{tstr} {vstr}\n")