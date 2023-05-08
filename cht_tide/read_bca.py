import os

import pandas as pd


class SfincsBoundary:
    def __init__(self):
        self.flow_boundary_points = []

    def read_flow_boundary_points(self, bnd_file: None):
        # Read SFINCS bnd file
        if not bnd_file:
            return

        if not os.path.exists(bnd_file):
            return

        # Read the bnd file
        df = pd.read_csv(
            bnd_file,
            index_col=False,
            header=None,
            delim_whitespace=True,
            names=["x", "y"],
        )

        # Loop through points
        for ind in range(len(df.x.values)):
            name = str(ind + 1).zfill(4)
            point = FlowBoundaryPoint(
                df.x.to_numpy()[ind], df.y.to_numpy()[ind], name=name
            )
            self.flow_boundary_points.append(point)

        return self

    def read_astro_boundary_conditions(self, bca_file):
        if not bca_file:
            return

        if not os.path.exists(bca_file):
            return

        d = IniStruct(filename=bca_file)
        for ind, point in enumerate(self.flow_boundary_points):
            point.astro = d.section[ind].data

        return self


# Classes for information about boundary points
class Point:
    def __init__(self, x, y, name=None, crs=None):
        self.x = x
        self.y = y
        self.crs = crs
        self.name = name
        self.data = None


class FlowBoundaryPoint:
    def __init__(self, x, y, name=None, crs=None, data=None, astro=None):
        self.name = name
        self.geometry = Point(x, y, crs=crs)
        self.data = data
        self.astro = astro


# Classes to read bca file
class Section:
    def __init__(self, name=None, keyword=[], data=None):
        self.name = None
        self.keyword = []
        self.data = None

    def get_value(self, keyword):
        for kw in self.keyword:
            if kw.name.lower() == keyword.lower():
                return kw.value


class Keyword:
    def __init__(self, name=None, value=None, comment=None):
        self.name = name
        self.value = value
        self.comment = comment


class IniStruct:
    def __init__(self, filename=None):
        self.section = []

        if filename:
            self.read(filename)

    def read(self, filename):
        import re

        self.section = []
        istart = []

        fid = open(filename, "r")
        lines = fid.readlines()
        fid.close()

        # First go through lines and find start of sections

        for i, line in enumerate(lines):
            ll = line.strip()
            if len(ll) == 0:
                continue
            if ll[0] == "[" and ll[-1] == "]":
                # new section
                section_name = ll[1:-1]
                sec = Section()
                sec.name = section_name
                istart.append(i)
                self.section.append(sec)

        # Now loop through sections
        for isec in range(len(self.section)):
            i1 = istart[isec] + 1
            if isec == len(self.section) - 1:
                i2 = len(lines)
            else:
                i2 = istart[isec + 1] - 1

            df = pd.DataFrame()

            # First keyword/value pairs
            for iline in range(i1, i2):
                ll = lines[iline].strip()

                if len(ll) == 0:
                    continue

                if ll[0] == "#":
                    # comment line
                    continue

                if "=" in ll:
                    # Must be key/val pair
                    key = Keyword()

                    # First find comment
                    if "#" in ll:
                        ipos = [(i.start()) for i in re.finditer("#", ll)]
                        if len(ipos) > 1:
                            # data in between first to #
                            # remove first two #
                            ll = (
                                ll[0 : ipos[0]]
                                + ll[ipos[0] + 1 : ipos[1]]
                                + ll[ipos[1] + 1 :]
                            )

                    if "#" in ll:
                        j = ll.index("#")
                        key.comment = ll[j + 1 :].strip()
                        ll = ll[0:j].strip()

                    # Now keyword and value
                    tx = ll.split("=")
                    key.name = tx[0].strip()
                    key.value = tx[1].strip()

                    self.section[isec].keyword.append(key)

                else:
                    # And now for the data
                    a_list = ll.split()
                    list_of_floats = []
                    for item in a_list:
                        try:
                            list_of_floats.append(float(item))
                        except:  # noqa: E722
                            list_of_floats.append(item)
                    a_series = pd.Series(list_of_floats)
                    df = pd.concat([df, a_series], axis=1)

            if not df.empty:
                df = df.transpose()
                df = df.set_index([0])
                self.section[isec].data = df
