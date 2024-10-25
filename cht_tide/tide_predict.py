# -*- coding: utf-8 -*-
"""
Created on Wed May 19 14:25:56 2021

@author: ormondt
"""

import cht_tide.constituent as cons
from cht_tide.tide import Tide


def predict(data, times):
    all_constituents = [c for c in cons.noaa if c != cons._Z0]
    constituents = []
    amplitudes   = []
    phases       = []
    for name in data.index.to_list():
        okay = False
        noaa_name = name
        if name == "MM":
            noaa_name = "Mm"
        if name == "MF":
            noaa_name = "Mf"
        if name == "SA":
            noaa_name = "Sa"
        if name == "SSA":
            noaa_name = "Ssa"
        if name == "MU2":
            noaa_name = "mu2"
        if name == "NU2":
            noaa_name = "nu2"
        for cnst in all_constituents:
            if cnst.name == noaa_name:
                constituents.append(cnst)
                amplitudes.append(data.loc[name, "amplitude"])
                phases.append(data.loc[name, "phase"])
                okay = True                
                continue
        if not okay:    
            print(f"Constituent {name} not found in list of NOAA constituents ! Skipping ...")    

    td = Tide(
        constituents=constituents,
        amplitudes=amplitudes,
        phases=phases,
    )
    v = td.at(times)

    return v
