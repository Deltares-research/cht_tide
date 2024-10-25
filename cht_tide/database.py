# -*- coding: utf-8 -*-
"""
Created on Sun Apr 25 10:58:08 2021

@author: Maarten van Ormondt
"""

import os
import yaml
import toml

from .fes2014 import TideModelFes2014

class TideModelDatabase:
    """
    The main Tide Model Database class
    
    :param pth: Path name where bathymetry tiles will be cached.
    :type pth: string            
    """
    
    def __init__(self, path=None):
        self.path    = path
        self.dataset = []
        self.read()
    
    def read(self):
        """
        Reads meta-data of all datasets in the database. 
        """
        if self.path is None:
            print("Path to tide model database not set !")
            return
        
        # Read in database
        tml_file = os.path.join(self.path, "tidemodels.tml")
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


def dict2yaml(file_name, dct, sort_keys=False):
    yaml_string = yaml.dump(dct, sort_keys=sort_keys)    
    file = open(file_name, "w")  
    file.write(yaml_string)
    file.close()

def yaml2dict(file_name):
    file = open(file_name,"r")
    dct = yaml.load(file, Loader=yaml.FullLoader)
    return dct
