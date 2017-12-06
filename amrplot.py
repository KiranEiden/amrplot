#!/usr/bin/env python3

import matplotlib as mpl
mpl.use("QT4Agg")

import matplotlib.pyplot as plt

import readline
import re
import sys

import yt
import yt.utilities.exceptions as yt_except

# assume that our data is in CGS
from yt.units import cm

if sys.version_info.major == 2:
    input = raw_input

#plt.ion()
yt.toggle_interactivity()

# look at this for history persistence (using atexit):
# https://gist.github.com/thanhtphung/20980ebee86e24933b13
readline.parse_and_bind("tab: complete")
readline.parse_and_bind('set editing-mode emacs')

yt.funcs.mylog.setLevel(0)

PROMPT = "> "

COMMANDS = ["help",
            "load",
            "listvar",
            "plot",
            "quit",
            "replot",
            "reset",
            "save",
            "set"]

class FileInfo(object):
    """ cache the file info so we don't have to continually load things """

    def __init__(self):
        self.name = None
        self.varlist = None
        self.ds = None
        self.is_axisymmetric = False
        self.dim = -1

    def load(self, filename):
        filename = filename.replace("\"", "").replace("'", "")

        # only load if it is a new file
        if filename != self.name:
            self.name = filename
            print("trying to open: {}", self.name)
            try:
                self.ds = yt.load(self.name)
            except yt_except.YTOutputNotIdentified:
                print("file unable to be opened\n")
                self.name = None

            self.varlist = self.ds.field_list
            self.is_axisymmetric = self.ds.geometry == "cylindrical"
            if self.ds.domain_dimensions[2] == 1:
                self.dim = 2
            else:
                self.dim = 3

    def file_loaded(self, msg=None):

        if self.name is None:
            if msg is not None:
                print(msg)
            return False

        return True

class State(object):
    """ keep track of the current state of the plot, limits, etc"""

    def __init__(self, file_info):
        self.file_info = file_info

        # Coordinate limits
        self.xbounds = None
        self.ybounds = None
        self.zbounds = None

        # Variable limits
        self.varname = None
        self.vbounds = None

        self.current_plot_object = None

        # Settings
        self.log = False
        self.show_grid = False
        self.center = None
        self.normal = "z"

    def get_center(self):
        """ get the coordinates of the center of the plot """
        if self.center is not None:
            return self.center

        if self.xbounds is None:
            xctr = 0.5*(self.file_info.ds.domain_left_edge[0] + 
                        self.file_info.ds.domain_right_edge[0])
        else:
            xctr = 0.5*(self.xbounds[0] + self.xbounds[1])

        if self.ybounds is None:
            yctr = 0.5*(self.file_info.ds.domain_left_edge[1] + 
                        self.file_info.ds.domain_right_edge[1])
        else:
            yctr = 0.5*(self.ybounds[0] + self.ybounds[1])
        print("yctr = ", yctr)

        if self.file_info.dim == 2:
            zctr = 0.0
        else:
            if self.zbounds is None:
                zctr = 0.5*(self.file_info.ds.domain_left_edge[2] + 
                            self.file_info.ds.domain_right_edge[2])
            else:
                zctr = 0.5*(self.zbounds[0] + self.zbounds[1])

        return xctr, yctr, zctr

    def get_width(self):
        """ get the width of the plot """

        if self.xbounds is None:
            xwidth = (self.file_info.ds.domain_right_edge[0] -
                      self.file_info.ds.domain_left_edge[0]).in_cgs()
        else:
            xwidth = (self.xbounds[1] - self.xbounds[0])*cm

        if self.ybounds is None:
            ywidth = (self.file_info.ds.domain_right_edge[1] -
                      self.file_info.ds.domain_left_edge[1]).in_cgs()
        else:
            ywidth = (self.ybounds[1] - self.ybounds[0])*cm

        if self.file_info.dim == 2:
            zwidth = 0.0
        else:
            if self.zbounds is None:
                zwidth = (self.file_info.ds.domain_right_edge[2] -
                          self.file_info.ds.domain_left_edge[2]).in_cgs()
            else:
                zwidth = (self.zbounds[1] - self.zbounds[0])*cm

        return xwidth, ywidth, zwidth


    def get_normal(self):
        """ Returns the normal vector for the state object. """

        return "theta" if self.file_info.is_axisymmetric else self.normal

    def is_off_axis(self):
        """ Returns false if the normal is set to a coordinate axis or the plot is axisymmetric, true otherwise. """

        if self.normal != "theta" and self.file_info.is_axisymmetric:
            print("alternate normal setting cannot be applied to axisymmetric plots")

        def converter(element):
            return element if element is 0 else 1

        return not (sum(map(converter, self.normal)) == 1 or self.file_info.is_axisymmetric)


    def reset(self):
        """ Reset the data in the State object """

        self.__init__(self.file_info)

def load_cmd(ss, pp):
    """ load command takes one argument: plotfile"""

    if check_arg_error(pp, 1):
        return

    ss.file_info.load(pp[0])

def listvar_cmd(ss, pp):
    """ listvar command takes up to a single argument: plotfile """

    if check_arg_error(pp, 0, 1):
        return

    if len(pp) == 1:
        filename = pp[0]
        ss.file_info.load(filename)
        msg = None
    else:
        msg = "a file must be specified if one has not been loaded"

    if ss.file_info.file_loaded(msg):
        for f in ss.file_info.varlist:
            print(f)


def plot_cmd(ss, pp):
    """ plot command takes 1 or 2 arguments: plotfile (optional), variable name """

    if check_arg_error(pp, 1, 2):
        return

    if len(pp) == 2:
        ss.file_info.load(pp[0])
        ds = ss.file_info.ds
        msg = None
        var = pp[1]
    else:
        ds = ss.file_info.ds
        msg = "a file must be specified if one has not been loaded"
        var = pp[0]

    if not ss.file_info.file_loaded(msg):
        return

    if var.startswith("'") and var.endswith("'") or var.startswith('"') and var.endswith('"'):
        var = var[1:-1]

    if var in ss.file_info.ds.fields.gas or ('boxlib', var) in ds.field_list:
        ss.varname = var
    else:
        print("invalid variable")
        return

    center = ss.get_center()
    width = ss.get_width()

    try:
        if ss.is_off_axis():
            slc = yt.SlicePlot(ds, ss.get_normal(), ss.varname, center=center, width=width)
        else:
            slc = yt.SlicePlot(ds, ss.get_normal(), ss.varname, origin="native", center=center, width=width)

        if ss.show_grid:
            try:
                slc.annotate_grids()
            except AttributeError:
                print("unable to show grid with current plot settings")

        slc.set_log(ss.varname, ss.log)

        plt.clf()
        slc.show()

    except IndexError:
        print("invalid variable")
        ss.varname = None
        return

    ss.current_plot_object = slc


def save_cmd(ss, pp):
    """ takes 1 argument: filename """

    if check_arg_error(pp, 1):
        return

    try:
        ofile = pp[0]
    except IndexError:
        print("no output file specified")
        return
    else:
        ofile.replace("'","").replace("\"","")

    if ss.current_plot_obj is not None:
        ss.current_plot_obj.save(ofile)
    else:
        print("must generate plot before saving")


def set_cmd(ss, pp):
    """ set takes a property and a set of values """

    settings = ["log", "xlim", "xrange", "ylim", "yrange", "zlim", "zrange", "grid", "center", "normal"]
    setting = pp[0].lower()

    if setting not in settings:
        print("{} not supported, setting must be in: {}".format(setting, settings))
        return

    true = ["true", "1", "on", "t"]
    false = ["false", "0", "off", "f"]

    if setting == "log":
        if check_arg_error(pp, 2):
            return
        if pp[1].lower() in true:
            ss.log = True
        elif pp[1].lower() in false:
            ss.log = False
        else:
            print("input must be in {} or {}".format(true, false))

    elif setting in ["xlim", "xrange", "ylim", "yrange", "zlim", "zrange"]:
        is_x = False
        is_y = False
        is_z = False

        if pp[0].lower().startswith("x"):
            is_x = True
        elif pp[0].lower().startswith("y"):
            is_y = True
        elif pp[0].lower().startswith("z"):
            is_z = True

        try:
            nmin, nmax = map(float, parse_tuple(pp, 1))
            if nmin > nmax:
                raise ValueError("min ({}) must be less than max ({})".format(nmin, nmax))
        except (ValueError, IndexError) as err:
            print(err)
            return

        if is_x:
            ss.xbounds = (nmin, nmax)
        elif is_y:
            ss.ybounds = (nmin, nmax)
        elif is_z:
            ss.zbounds = (nmin, nmax)

    elif setting == "grid":
        if check_arg_error(pp, 2):
            return
        if pp[1].lower() in true:
            ss.show_grid = True
        elif pp[1].lower() in false:
            ss.show_grid = False
        else:
            print("input must be in {} or {}".format(true, false))

    elif setting == "center":
        try:
            x, y, z = map(float, parse_tuple(pp, 1))
        except (ValueError, IndexError) as err:
            print(err)
        else:
            ss.center = (x, y, z)

    elif setting == "normal":
        if len(pp) == 2:
            if pp[1] not in ["x", "y", "z"]:
                print("invalid normal vector direction")
            else:
                ss.normal = pp[1]
            return

        try:
            x, y, z = map(float, parse_tuple(pp, 1))
        except (ValueError, IndexError) as err:
            print(err)
        else:
            if (x, y, z) == (0, 0, 0):
                print("normal vector cannot be zero vector")
            else:
                ss.normal = (x, y, z)


def replot_cmd(ss, pp):
    """ replot the current plot with new settings """

    if check_arg_error(pp, 0):
        return
    if ss.varname is None:
        print("must plot first to use replot command")
        return

    plot_cmd(ss, [ss.file_info.name, ss.varname])


def reset_cmd(ss, pp):
    """ Reset the plot attributes """

    if check_arg_error(pp, 0):
        return
    ss.reset()

def check_arg_error(pp, *numargs):
    """ Checks for an illegal number of arguments, returning whether the number of args was legal or not. """

    if len(pp) not in numargs:
        numargs = " or ".join(map(str, numargs))
        print("command requires {} argument(s), {} given".format(numargs, len(pp)))
        return True

    return False

def parse_tuple(pp, startIndex, endIndex=None):
    """ Helper method for handling a tuple of arguments. Raises index error if the indices were invalid, value error
    if the tuple was invalid. Uses slicing - string to parse is inclusive of startIndex and exclusive of endIndex."""

    try:
        delim_str = " ".join(pp[startIndex:]) if endIndex is None else " ".join(pp[startIndex:endIndex])

        # Replace brackets
        valid_brackets = ["(", ")", "[", "]", "{", "}", "<", ">"]
        regEx = "|".join(map(re.escape, valid_brackets))
        delim_str = re.sub(regEx, "", delim_str)

        # Handle multiple delimiters -- from stack overflow
        return tuple(filter(None, re.split("[, ;]+", delim_str)))

    except ValueError:
        raise ValueError("unable to parse list argument, check syntax")
    except IndexError:
        raise IndexError("unable to read delimited list, expected as argument number {}".format(startIndex + 1))

def main():

    print("Welcome to amrplot.  Type 'help' for a list of commands.\n")

    ff = FileInfo()
    ss = State(ff)

    while True:

        cmd_str = input(PROMPT)

        if cmd_str == "":
            continue

        parts = cmd_str.split()
        command = parts[0].lower()

        # every function takes a file object, a state object, and any commands

        if command not in COMMANDS:
            print("invalid command\n")
            continue

        if command == "help":
            for c in COMMANDS:
                print(c)
            print("")

        elif command == "quit":
            sys.exit("Good bye!")

        else:
            fname = "{}_cmd".format(command)
            this_module = sys.modules[__name__]
            method_to_call = getattr(this_module, fname)
            method_to_call(ss, parts[1:])
            print("")

if __name__ == "__main__":
    main()
