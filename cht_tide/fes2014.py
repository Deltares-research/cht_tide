# -*- coding: utf-8 -*-
"""
Created on Sun Apr 25 10:58:08 2021

@author: Maarten van Ormondt
"""
import os
import xarray as xr

from .model import TideModel

class TideModelFes2014(TideModel):
    """
    """

    def __init__(self, name, path):
        super().__init__()
        
        self.name              = name
        self.path              = path
        # self.local_path        = path
        self.read_metadata()
        self.get_constituents()
    
    def get_constituents(self):
        """
        Get constituents from nc file names in path
        """
        # Loop through nc files in path
        # Get constituents from file names
        filenames = os.listdir(self.path)
        self.constituents = []
        for filename in filenames:
            if filename.endswith(".nc"):
                # Constituent is base name of file
                self.constituents.append(filename.split(".")[0].upper())

    def get_data(self, xl, yl, constituents="all"):
        """
        """
        if constituents == "all":
            constituents = self.constituents

        nconst = len(constituents)

        if xl[0] < 0.0 and xl[1] < 0.0:
            xl = [xl[0] + 360.0, xl[1] + 360.0]

        # Make empty dataset with arrays amplitude and phase, and dimensions lon, lat, and constituent
        ds = xr.Dataset()

        # Get dimensions from first file
        filename = os.path.join(self.path, f"{constituents[0]}.nc")
        ds0 = xr.open_dataset(filename).sel(lon=slice(xl[0], xl[1]), lat=slice(yl[0], yl[1]))
        lon = ds0.lon
        lat = ds0.lat
        ds0.close()
        # Set constituent dimension
        ds["constituent"] = constituents
        # Set lon and lat dimensions
        ds["lon"] = lon
        ds["lat"] = lat
        # Set amplitude and phase arrays
        ds["amplitude"] = xr.DataArray(data=nconst*[len(lat)*[len(lon)*[0.0]]], dims=["constituent", "lat", "lon"])
        ds["phase"] = xr.DataArray(data=nconst*[len(lat)*[len(lon)*[0.0]]], dims=["constituent", "lat", "lon"])

        ds0.close()

        # Loop through constituents
        for constituent in constituents:
            # Get data for constituent
            filename = os.path.join(self.path, f"{constituent}.nc")
            ds0 = xr.open_dataset(filename).sel(lon=slice(xl[0], xl[1]), lat=slice(yl[0], yl[1]))
            # Add data to xarray dataset
            ds["amplitude"].loc[constituent] = ds0["amplitude"].values / 100.0 # Convert cm to m
            ds["phase"].loc[constituent] = ds0["phase"].values
            ds0.close()
        
        return ds

