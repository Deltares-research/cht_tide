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
    for name in data.index.to_list():
        if name == "MM":
            name = "Mm"
        if name == "MF":
            name = "Mf"
        if name == "SA":
            name = "Sa"
        if name == "SSA":
            name = "Ssa"
        if name == "MU2":
            name = "mu2"
        if name == "NU2":
            name = "nu2"
        for cnst in all_constituents:
            if cnst.name == name:
                constituents.append(cnst)
                continue

    td = Tide(
        constituents=constituents,
        amplitudes=data.iloc[:, 0].to_list(),
        phases=data.iloc[:, 1].to_list(),
    )
    v = td.at(times)

    return v
    return v
