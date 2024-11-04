# -*- coding: utf-8 -*-
"""
Created on Sun Apr 25 10:58:08 2021

@author: Maarten van Ormondt
"""

import os
import yaml
import toml
import boto3
from botocore import UNSIGNED
from botocore.client import Config

from .fes2014 import TideModelFes2014

class TideModelDatabase:
    """
    The main Tide Model Database class
    
    :param pth: Path name where bathymetry tiles will be cached.
    :type pth: string            
    """
    
    def __init__(self, path=None,
                 s3_bucket=None,
                 s3_key=None,
                 s3_region=None):
        self.path    = path
        self.dataset = []
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
            print("Path to tide model database not set !")
            return
        
        # Check if the path exists. If not, create it.
        if not os.path.exists(self.path):
            os.makedirs(self.path)

        # Read in database
        tml_file = os.path.join(self.path, "tide_models.tml")
        if not os.path.exists(tml_file):
            print("Warning! Tide model database file not found: " + tml_file)
            return

        datasets = toml.load(tml_file)

        for d in datasets["dataset"]:

            name = d["name"]

            if "path" in d:
                path = d["path"]
            else:
                path = os.path.join(self.path, name)

            # Read the meta data for this dataset
            fname = os.path.join(path, "metadata.tml")

            if os.path.exists(fname):
                metadata = toml.load(fname)
                dataset_format = metadata["format"]
            else:
                print("Could not find metadata file for dataset " + name + " ! Skipping dataset.")
                continue

            if dataset_format.lower() == "fes2014":
                model = TideModelFes2014(name, path)
            elif dataset_format.lower() == "tpxo_old":
                pass
            
            self.dataset.append(model)

    def check_online_database(self):
        if self.s3_client is None:
            self.s3_client = boto3.client('s3', config=Config(signature_version=UNSIGNED))
        if self.s3_bucket is None:
            return
        # First download a copy of bathymetry.tml and call it bathymetry_s3.tml
        key = f"{self.s3_key}/tide_models.tml"
        filename = os.path.join(self.path, "tide_models_s3.tml")
        print("Updating tide models database ...")
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
        tide_models_added = False
        added_names = []
        # Loop through s3 datasets, and check whether they exist in the local database.
        # If so, check if the metadata also exists. If not, make local folder and download the metadata.
        # Additionally, check if available_tiles.nc in s3 and not in local database, download it.
        for d in datasets_s3["dataset"]:
            # Get list of existing datasets
            s3_name = d["name"]
            if s3_name not in short_name_list:
                # Dataset not in local database
                print(f"Adding tide model {s3_name} to local database ...")
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
                    print(f"Failed to download {key}. Skipping tide model.")
                    continue
                # Necessary data has been downloaded    
                tide_models_added = True
                added_names.append(s3_name)
        # Write new local bathymetry.tml
        if tide_models_added:
            d = {}
            d["dataset"] = []
            for name in short_name_list:
                d["dataset"].append({"name": name})
            for name in added_names:
                d["dataset"].append({"name": name})
            # Now write the new bathymetry.tml
            with open(os.path.join(self.path, "tide_models.tml"), "w") as tml:
                toml.dump(d, tml)            
            # Read the database again
            self.dataset = []
            self.read()
        # else:
        #     print("No new tide models were added to the local database.")

    def get_dataset(self, name):
        for dataset in self.dataset:
            if dataset.name == name:
                return dataset
        return None

    def dataset_names(self):
        short_name_list = []
        long_name_list = []
        for dataset in self.dataset:
            short_name_list.append(dataset.name)
            long_name_list.append(dataset.long_name)
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
