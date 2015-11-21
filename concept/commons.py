# This file is part of CO𝘕CEPT, the cosmological 𝘕-body code in Python.
# Copyright © 2015 Jeppe Mosgaard Dakin.
#
# CO𝘕CEPT is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# CO𝘕CEPT is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with CO𝘕CEPT. If not, see http://www.gnu.org/licenses/
#
# The auther of CO𝘕CEPT can be contacted at
# jeppe.mosgaard.dakin(at)post.au.dk
# The latest version of CO𝘕CEPT is available at
# https://github.com/jmd-dk/concept/



# This module contains imports, Cython declarations and values
# of parameters common to all other modules. Each module should have
# 'from commons import *' as its first statement.



############################################
# Imports common to pure Python and Cython #
############################################
from __future__ import division  # Needed for Python3 division in Cython
# Miscellaneous modules
import collections, contextlib, ctypes, cython, imp, matplotlib, numpy as np, os, re
import shutil, sys, unicodedata
# For math
from numpy import (arange, asarray, concatenate, cumsum, delete, empty, linspace, loadtxt, ones,
                   unravel_index, zeros)
from numpy.random import random
# Use a matplotlib backend that does not require a running X-server
matplotlib.use('Agg')
# For plotting
import matplotlib.pyplot as plt
# When using ax.scatter in graphics.py (and possibly more) the following
# warning is given, as of NumPy 1.10.0 and 1.10.1, Matplotlib 1.4.3:
# FutureWarning: elementwise comparison failed; returning scalar instead,
# but in the future will perform elementwise comparison
#   if self._edgecolors == str('face'):
# This is a bug and will hopefully be fixed by the developers.
# In the meantime, as everything seems to be alright,
# suppress this warning.
import warnings
warnings.filterwarnings('ignore', category=FutureWarning)
# Import h5py. This has to be done after importing matplotlib, as this
# somehow makes libpng unable to find the zlib shared library.
import h5py
# For fancy terminal output
from blessings import Terminal
terminal = Terminal(force_styling=True)
terminal.CONCEPT = 'CO\x1b[3mN\x1b[23mCEPT'
# For timing
from time import time
from datetime import timedelta
# For development purposes only
from time import sleep



#############
# MPI setup #
#############
from mpi4py import MPI
cython.declare(master='bint',
               nprocs='int',
               rank='int',
               )
# Functions for communication
comm = MPI.COMM_WORLD
Allgather = comm.Allgather
Allgatherv = comm.Allgatherv
Allreduce = comm.Allreduce
Barrier = comm.Barrier
Bcast = comm.Bcast
Gather = comm.Gather
Gatherv = comm.Gatherv
Isend = comm.Isend
Reduce = comm.Reduce
Recv = comm.Recv
Scatter = comm.Scatter
Send = comm.Send
Sendrecv = comm.Sendrecv
allreduce = comm.allreduce
reduce = comm.reduce
sendrecv = comm.sendrecv
# Number of processes started with mpiexec
nprocs = comm.size
# The unique rank of the running process
rank = comm.rank
# Flag identifying the master/root process (that which have rank 0)
master = not rank

# Raised exceptions inside cdef functions do not generally propagte
# out to the caller. In places where exceptions are normally raised
# manualy, call this function with a descriptive message instead.
def abort(msg=''):
    masterwarn(msg, prefix='Aborting')
    sys.stderr.flush()
    sys.stdout.flush()
    comm.Abort(1)



###########
# C types #
###########
# Import the signed integer type ptrdiff_t
pxd = """
from libc.stddef cimport ptrdiff_t
"""
# C type names to NumPy dtype names
cython.declare(C2np='dict')
C2np = {# Booleans
        'bint': np.bool,
        # Integers
        'char'         : np.byte,
        'short'        : np.short,
        'int'          : np.intc,
        'long int'     : np.long,
        'long long int': np.longlong,
        'ptrdiff_t'    : np.intp,
        'Py_ssize_t'   : np.intp,
        # Unsgined integers
        'unsigned char'         : np.ubyte,
        'unsigned short'        : np.ushort,
        'unsigned int'          : np.uintc,
        'unsigned long int'     : np.uint,
        'unsigned long long int': np.ulonglong,
        'size_t'                : np.uintp,
        # Floating-point numbers
        'float'     : np.single,
        'double'    : np.double,
        'long float': np.longfloat,
        }
# In NumPy, binary operations between some unsigned int types (unsigned
# long int, unsigned long long int, size_t) and signed int types results
# in a double, rather than a signed int.
# Get around this bug by never using these particular unsigned ints.
if not cython.compiled:
    C2np['unsigned long int'] = C2np['long int']
    C2np['unsigned long long int'] = C2np['long long int']
    C2np['size_t'] = C2np['ptrdiff_t']



#####################
# Pure Python stuff #
#####################
# Definitions used by pure Python to understand Cython syntax
if not cython.compiled:
    # No-op decorators for Cython compiler directives
    def dummy_decorator(*args, **kwargs):
        if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
            # Called as @dummy_decorator. Return function
            return args[0]
        else:
            # Called as @dummy_decorator(*args, **kwargs).
            # Return decorator
            return dummy_decorator
    # Already builtin: cfunc, inline, locals, returns
    for directive in ('boundscheck',
                      'cdivision',
                      'initializedcheck',
                      'wraparound',
                      'header',
                      'pheader',
                      ):
        setattr(cython, directive, dummy_decorator)
    # Address (pointers into arrays)
    def address(a):
        dtype = re.search('ctypeslib\.(.*?)_Array', np.ctypeslib.as_ctypes(a).__repr__()).group(1)
        return a.ctypes.data_as(ctypes.POINTER(eval('ctypes.' + dtype)))
    setattr(cython, 'address', address)
    # C allocation syntax for memory management
    def sizeof(dtype):
        # C dtype names to Numpy dtype names
        if dtype in C2np:
            dtype = C2np[dtype]
        elif dtype in ('func_b_ddd',
                       'func_d_dd',
                       'func_d_ddd',
                       'func_ddd_ddd',
                       ):
            dtype='object'
        elif dtype[-1] == '*':
            # Allocate pointer array of pointers (eg. int**).
            # Emulate these as lists of arrays.
            return [empty(1, dtype=sizeof(dtype[:-1]).dtype)]
        elif master:
            abort(dtype + ' not implemented as a Numpy dtype in commons.py')
        return np.array([1], dtype=dtype)
    def malloc(a):
        if isinstance(a, list):
            # Pointer to pointer represented as list of arrays
            return a
        return empty(a[0], dtype=a.dtype)
    def realloc(p, a):
        # Reallocation of pointer assumed
        p.resize(a[0], refcheck=False)
        return p
    def free(a):
        pass
    # Casting
    def cast(a, dtype):
        match = re.search('(.*)\[', dtype)
        if match:
            # Pointer to array cast assumed
            # (array to array in pure Python).
            return a
        else:
            # Scalar
            return C2np[dtype](a)
    # Dummy fused types
    number = number2 = integer = floating = signed_number = signed_number2 = number_mv = []
    # Mathematical functions
    from numpy import (sin, cos, tan,
                       arcsin,  arccos, arctan,
                       sinh, cosh, tanh,
                       arcsinh, arccosh, arctanh,
                       exp, log, log2, log10,
                       sqrt,
                       round,
                       )
    from math import erf, erfc
    # Dummy ℝ dict for constant expressions
    class DummyDict(dict):
        def __getitem__(self, key):
            return key
    ℝ = DummyDict()
    # The cimport function, which in the case of pure Python should
    # simply execute the statements parsed to it as a string.
    cimport = exec



###################################
# Cython imports and declarations #
###################################
pxd = """
# Get full access to all of Cython
cimport cython
# GNU Scientific Library
from cython_gsl cimport *
# Functions for manual memory management
from cpython.mem cimport PyMem_Malloc, PyMem_Realloc, PyMem_Free
# Function type definitions of the form func_returntype_argumenttypes
ctypedef bint    (*func_b_ddd)  (double, double, double)
ctypedef double  (*func_d_dd)   (double, double)
ctypedef double  (*func_d_ddd)  (double, double, double)
ctypedef double* (*func_ddd_ddd)(double, double, double)
# Create a fused number type containing all necessary numerical types
ctypedef fused number:
    cython.int
    cython.size_t
    cython.Py_ssize_t
    cython.float
    cython.double
# Create another fused number type, so that function arguments can have
# different specializations.
ctypedef fused number2:
    cython.int
    cython.size_t
    cython.Py_ssize_t
    cython.float
    cython.double
# Create integer and floating fused types
ctypedef fused integer:
    cython.int
    cython.size_t
    cython.Py_ssize_t
ctypedef fused floating:
    cython.float
    cython.double
# Create two identical signed number fused types
ctypedef fused signed_number:
    cython.int
    cython.float
    cython.double
ctypedef fused signed_number2:
    cython.int
    cython.float
    cython.double
# Mathematical functions
from libc.math cimport (sin, cos, tan,
                        asin as arcsin, 
                        acos as arccos, 
                        atan as arctan,
                        sinh, cosh, tanh,
                        asinh as arcsinh, 
                        acosh as arccosh, 
                        atanh as arctanh,
                        exp, log, log2, log10,
                        sqrt, erf, erfc,
                        round,
                        )
"""



#############
# Constants #
#############
cython.declare(machine_ϵ='double',
               π='double',
               )
machine_ϵ = np.finfo(C2np['double']).eps
π = np.pi



##################
# Physical units #
##################
# The names of the three base units
cython.declare(base_length='str',
               base_time='str',
               base_mass='str',
               )
base_length = 'Mpc'
base_time = 'Gyr'
base_mass = '1e+10*m_sun'
# Python class storing the values of all units as class attributes
class Units_class():
    # Values of base units
    pc     = 1e-6
    yr     = 1e-9
    m_sun  = 1e-10
    # Prefixes of the base units
    kpc    = 1e+3*pc
    Mpc    = 1e+6*pc
    Gpc    = 1e+9*pc
    kyr    = 1e+3*yr
    Myr    = 1e+6*yr
    Gyr    = 1e+9*yr
    km_sun = 1e+3*m_sun
    Mm_sun = 1e+6*m_sun
    Gm_sun = 1e+9*m_sun
    # Square and cubic parsecs
    pc2     = pc**2
    kpc2    = kpc**2
    Mpc2    = Mpc**2
    Gpc2    = Gpc**2
    pc3     = pc**3
    kpc3    = kpc**3
    Mpc3    = Mpc**3
    Gpc3    = Gpc**3
    # Non-base units
    AU      = π/(60*60*180)*pc
    m       = AU/149597870700
    cm      = 1e-2*m
    km      = 1e+3*m
    day     = yr/365.25  # Uses Julian years
    hr      = day/24
    minutes = hr/60
    s       = minutes/60
    kg      = m_sun/1.989e+30
    g       = 1e-3*kg
    # Make instance creation possible (though superfluous)
    def __init__(self, **kwargs):
        pass
# In the case of pure Python, use Units_class directly
if not cython.compiled:
    Units = Units_class
# In the case of Cython, use a struct to hold the units
pxd = """
ctypedef struct Units:
    # Base units
    double pc, yr, m_sun
    # Prefixes of the base units
    double kpc, Mpc, Gpc
    double kyr, Myr, Gyr
    double km_sun, Mm_sun, Gm_sun
    # Square and cubic parsecs
    double pc2, kpc2, Mpc2, Gpc2
    double pc3, kpc3, Mpc3, Gpc3
    # Non-base units
    double AU, m, cm, km
    double day, hr, minutes, s
    double kg, g
"""
# Instantiate the Units_class instance (Python) / struct (Cython)
cython.declare(units='Units')
units = Units(# Base units
              pc     = Units_class.pc,
              yr     = Units_class.yr,
              m_sun  = Units_class.m_sun,
              # Prefixes of the base units
              kpc    = Units_class.kpc,
              Mpc    = Units_class.Mpc,
              Gpc    = Units_class.Gpc,
              kyr    = Units_class.kyr,
              Myr    = Units_class.Myr,
              Gyr    = Units_class.Gyr,
              km_sun = Units_class.km_sun,
              Mm_sun = Units_class.Mm_sun,
              Gm_sun = Units_class.Gm_sun,
              # Square and cubic parsecs
              pc2     = Units_class.pc2,
              kpc2    = Units_class.kpc2,
              Mpc2    = Units_class.Mpc2,
              Gpc2    = Units_class.Gpc2,
              pc3     = Units_class.pc3,
              kpc3    = Units_class.kpc3,
              Mpc3    = Units_class.Mpc3,
              Gpc3    = Units_class.Gpc3,
              # Non-base units
              AU      = Units_class.AU,
              m       = Units_class.m,
              cm      = Units_class.cm,
              km      = Units_class.km,
              day     = Units_class.day,
              hr      = Units_class.hr,
              minutes = Units_class.minutes,
              s       = Units_class.s,
              kg      = Units_class.kg,
              g       = Units_class.g,
              )
# Grab the dict from the Units_class and store it separately
cython.declare(units_dict='dict')
units_dict = {key: val for key, val in Units_class.__dict__.items() if not key.startswith('_')}



###########################################
# Absolute paths to directories and files #
###########################################
# The paths are stored in the top_dir/.paths file
cython.declare(paths='dict')
top_dir = os.path.abspath('.')
while True:
    if '.paths' in os.listdir(top_dir):
        break
    elif master and top_dir == '/':
        abort('Cannot find the .paths file!')
    top_dir = os.path.dirname(top_dir)
paths_module = imp.load_source('paths', top_dir + '/.paths')
paths = {key: value for key, value in paths_module.__dict__.items()
         if isinstance(key, str) and not key.startswith('__')}
# Function for converting an absolute path to its "sensible" form.
# That is, this function returns the relative path with respect to the
# concept directory, if it is no more than one directory above the
# concept directory. Otherwise, return the absolute path back again.
@cython.header(# Arguments
               path='str',
               # Locals
               relpath='str',
               returns='str',
               )
def sensible_path(path):
    if not path:
        return path
    relpath = os.path.relpath(path, paths['concept_dir'])
    if relpath.startswith('../../'):
        return path
    return relpath



##########################
# Command line arguments #
##########################
# Handle command line arguments given to the Python interpreter
# (not those explicitly given to the run script).
# Construct a dict from command line arguments of the form
# "params='/path/to/params'"
cython.declare(argd='dict',
               globals_dict='dict',
               scp_password='str',
               )
argd = {}
for arg in sys.argv:
    with contextlib.suppress(Exception):
        exec(arg, argd)
globals_dict = {}
exec('', globals_dict)
for key in globals_dict.keys():
    argd.pop(key, None)
# Extract command line arguments from the dict. If not given,
# give the arguments some default value.
# The parameter file
paths['params'] = argd.get('params', '')
paths['params_dir'] = '' if not paths['params'] else os.path.dirname(paths['params'])
# The scp password
scp_password = argd.get('scp_password', '')



########################
# The unicode function #
########################
# The pyxpp script convert all Unicode source code characters into
# ASCII. The function below grants the code access to
# Unicode string literals, by undoing the convertion.
if not cython.compiled:
    # Dummy unicode function for pure Python
    def unicode(c):
        return c
else:
    """
    @cython.header(c='str', returns='str')
    def unicode(c):
        if len(c) > 10 and c.startswith('__UNICODE__'):
            c = c[11:]
        c = c.replace('__space__', ' ')
        c = c.replace('__dash__', '-')
        return unicodedata.lookup(c)
    """



################################################################
# Import all user specified parameters from the parameter file #
################################################################
# Dict constituting the namespace for the statements
# in the user specified parameter file.
# Everything from NumPy should be available when defining parameters
params = vars(np)
# Units from the units extension type should be available
# when defining parameters.
params.update(units_dict)
# Additional things which should be available when defining parameters
params.update({# The paths dict
               'paths': paths,
               # Modules
               'numpy': np,
               'np'   : np,
               'os'   : os,
               're'   : re,
               'sys'  : sys,
               # Unicode variables
               unicode('π'): π,
               # Constants
               'pi'       : π,
               'machine_ϵ': machine_ϵ,
               })
# "Import" the parameter file by executing it
# in the namespace defined by the params dict.
if os.path.isfile(paths['params']):
    with open(paths['params'], encoding='utf-8') as params_file:
        exec(params_file.read(), params)
# The parameters are now being processed as follows:
# - Some parameters are explicitly casted.
# - Spaces are removed from the 'snapshot_type' parameter, and all
#   characters are converted to lowercase.
# - The 'output_times' are sorted and duplicates (for each type of
#   output) are removed.
# - Paths below or just one level above the concept directory are made
#   relative to this directory in order to reduce screen clutter.
# - The 'special_params' parameter is set to an empty dictionary if it
#   is not defined in params.py.
# - Colors are transformed to (r, g, b) arrays. Below is the function
#   that handles the color input.
def to_rgb(value):
    if isinstance(value, int) or isinstance(value, float):
        value = str(value)
    return np.array(matplotlib.colors.ColorConverter().to_rgb(value), dtype=C2np['double'])
cython.declare(# Input/output
               IC_file='str',
               snapshot_type='str',
               output_dirs='dict',
               output_bases='dict',
               output_times='dict',
               # Numerical parameter
               boxsize='double',
               ewald_gridsize='Py_ssize_t',
               PM_gridsize='ptrdiff_t',
               P3M_scale='double',
               P3M_cutoff='double',
               softeningfactors='dict',
               Δt_factor='double',
               R_tophat='double',
               # Cosmological parameters
               H0='double',
               Ωm='double',
               ΩΛ='double',
               a_begin='double',
               # Graphics
               powerspec_plot='bint',
               color='double[::1]',
               bgcolor='double[::1]',
               resolution='unsigned int',
               liverender='str',
               remote_liverender='str',
               terminal_colormap='str',
               terminal_resolution='unsigned int',
               # Simlation options
               kick_algorithms='dict',
               use_Ewald='bint',
               use_PM='bint',
               use_P3M='bint',
               fftw_rigor='str',
               # Hidden parameters
               special_params='dict',
               )
# Input/output
IC_file = sensible_path(str(params.get('IC_file', '')))
snapshot_type = (str(params.get('snapshot_type', 'standard'))
                 .lower().replace(' ', ''))
output_dirs = dict(params.get('output_dirs', {}))
for kind in ('snapshot', 'powerspec', 'render'):
    output_dirs[kind] = str(output_dirs.get(kind, paths['output_dir']))
    if not output_dirs[kind]:
        output_dirs[kind] = paths['output_dir']
output_dirs = {key: sensible_path(path) for key, path in output_dirs.items()}
output_bases = dict(params.get('output_bases', {}))
for kind in ('snapshot', 'powerspec', 'render'):
    output_bases[kind] = str(output_bases.get(kind, kind))
output_times = dict(params.get('output_times', {}))
for kind in ('snapshot', 'powerspec', 'render', 'terminal render'):
    output_times[kind] = output_times.get(kind, ())
output_times = {key: tuple(sorted(set([float(nr) for nr in (list(val) if hasattr(val, '__iter__')
                                                                 and not hasattr(val, '__len__')
                                                            else np.ravel(val))
                                       if nr or nr == 0])))
                for key, val in output_times.items()}
# Numerical parameters
boxsize = float(params.get('boxsize', 1))
ewald_gridsize = int(params.get('ewald_gridsize', 64))
PM_gridsize = int(params.get('PM_gridsize', 64))
P3M_scale = float(params.get('P3M_scale', 1.25))
P3M_cutoff = float(params.get('P3M_cutoff', 4.8))
softeningfactors = dict(params.get('softeningfactors', {}))
for kind in ('dark matter', ):
    softeningfactors[kind] = float(softeningfactors.get(kind, 0.03))
Δt_factor = float(params.get(unicode('Δ') + 't_factor', 0.01))
R_tophat = float(params.get('R_tophat', 8*units.Mpc))
# Cosmological parameters
H0 = float(params.get('H0', 70*units.km/(units.s*units.Mpc)))
Ωm = float(params.get(unicode('Ω') + 'm', 0.3))
ΩΛ = float(params.get(unicode('Ω') + unicode('Λ'), 0.7))
a_begin = float(params.get('a_begin', 0.02))
# Graphics
powerspec_plot = bool(params.get('powerspec_plot', False))
color = to_rgb(params.get('color', 'lime'))
bgcolor = to_rgb(params.get('bgcolor', 'black'))
resolution = int(params.get('resolution', 1080))
liverender = sensible_path(str(params.get('liverender', '')))
if liverender and not liverender.endswith('.png'):
    liverender += '.png'
remote_liverender = str(params.get('remote_liverender', ''))
if remote_liverender and not remote_liverender.endswith('.png'):
    remote_liverender += '.png'
terminal_colormap = str(params.get('terminal_colormap', 'gnuplot2'))
terminal_resolution = int(params.get('terminal_resolution', 80))
# Simulation options
kick_algorithms = dict(params.get('kick_algorithms', {}))
for kind in ('dark matter', ):
    kick_algorithms[kind] = str(kick_algorithms.get(kind, 'PP'))
use_Ewald = bool(params.get('use_Ewald', False))
if (set(('PM', 'P3M')) & set(kick_algorithms.values())
    or output_times['powerspec']):
    use_PM = bool(params.get('use_PM', True))
else:
    use_PM = bool(params.get('use_PM', False))
if 'P3M' in kick_algorithms.values():
    use_P3M = bool(params.get('use_P3M', True))
else:
    use_P3M = bool(params.get('use_P3M', False))
fftw_rigor = params.get('fftw_rigor', 'estimate').lower()
# Extra hidden parameters via the special_params variable
special_params = dict(params.get('special_params', {}))

# Output times very close to a_begin are probably meant to be at a_begin
output_times = {key: tuple([(a_begin if np.abs(nr - a_begin) < 10*machine_ϵ else nr)
                            for nr in val])
                for key, val in output_times.items()}



######################
# Global allocations #
######################
# Useful for temporary storage of 3D vector
cython.declare(vector='double*',
               vector_mv='double[::1]',
               )
vector = malloc(3*sizeof('double'))
vector_mv = cast(vector, 'double[:3]')



############################################
# Derived and internally defined constants #
############################################
cython.declare(a_dumps='tuple',
               a_max='double',
               G_Newton='double',
               PM_gridsize3='long long int',
               PM_gridsize_padding='ptrdiff_t',
               ewald_file='str',
               powerspec_dir='str',
               powerspec_base='str',
               powerspec_times='tuple',
               render_dir='str',
               render_base='str',
               render_times='tuple',
               scp_host='str',
               snapshot_dir='str',
               snapshot_base='str',
               snapshot_times='tuple',
               terminal_render_times='tuple',
               ϱ='double',
               ϱm='double',
               PM_fac_const='double',
               longrange_exponent_fac='double',
               P3M_cutoff_phys='double',
               P3M_scale_phys='double',
               )
# List of dump times
a_dumps = tuple(sorted(set([nr for val in output_times.values() for nr in val])))
# The scale factor at the last time step
a_max = a_begin if len(a_dumps) == 0 else np.max(a_dumps)
# Extract output variables from output dicts
snapshot_dir          = output_dirs['snapshot']
snapshot_base         = output_bases['snapshot']
snapshot_times        = output_times['snapshot']
powerspec_dir         = output_dirs['powerspec']
powerspec_base        = output_bases['powerspec']
powerspec_times       = output_times['powerspec']
render_dir            = output_dirs['render']
render_base           = output_bases['render']
render_times          = output_times['render']
terminal_render_times = output_times['terminal render']
# Newtons constant
G_Newton = 6.6738e-11*units.m**3/units.kg/units.s**2
# The average, comoing density (the critical
# comoving density since we only study flat universes)
ϱ = 3*H0**2/(8*π*G_Newton)
# The average, comoving matter density
ϱm = Ωm*ϱ
# The real size of the padded dimension of PM_gridsize
PM_gridsize_padding = 2*(PM_gridsize//2 + 1)
# The cube of PM_gridsize. This is defined here because it is a very
# large integer (long long int), making the ℝ-syntax unpractical
PM_gridsize3 = cast(PM_gridsize, 'long long int')**3
# Name of file storing the Ewald grid
ewald_file = '.ewald_gridsize=' + str(ewald_gridsize) + '.hdf5'
# All constant factors across the PM scheme is gathered in the PM_fac
# variable. It's contributions are:
# For CIC interpolating particle masses/volume to the grid points:
#     particles.mass/(boxsize/PM_gridsize)**3
# Normalization due to forwards and backwards Fourier transforms:
#     1/PM_gridsize**3
# Factor in the Greens function:
#     -4*π*G_Newton/((2*π/((boxsize/PM_gridsize)*PM_gridsize))**2)   
# From finite differencing to get the forces:
#     -PM_gridsize/boxsize
# For converting acceleration to momentum
#     particles.mass*Δt
# Everything except the mass and the time are constant, and is condensed
# into the PM_fac_const variable.
PM_fac_const = G_Newton*PM_gridsize/(π*boxsize**2)
# The exponential cutoff for the long-range force looks like
# exp(-k2*rs2). In the code, the wave vector is in grid units in stead
# of radians. The conversion is 2*π/PM_gridsize. The total factor on k2
# in the exponential is then
longrange_exponent_fac = -(2*π/PM_gridsize*P3M_scale)**2
# The short-range/long-range force scale
P3M_scale_phys = P3M_scale*boxsize/PM_gridsize
# Particles within this distance to the surface of the domain should
# interact with particles in the neighboring domain via the shortrange
# force, when the P3M algorithm is used.
P3M_cutoff_phys = P3M_scale_phys*P3M_cutoff
# The host name in the 'remote_liverender' parameter
scp_host = re.search('@(.*):', remote_liverender).group(1) if remote_liverender else ''



############################
# Custom defined functions #
############################
# Absolute function for numbers
if not cython.compiled:
    # Use NumPy's abs function in pure Python
    max = np.max
else:
    @cython.header(x=signed_number,
                   returns=signed_number,
                   )
    def abs(x):
        if x < 0:
            return -x
        return x

# Max function for 1D memory views of numbers
if not cython.compiled:
    # Use NumPy's max function in pure Python
    max = np.max
else:
    """
    @cython.header(returns=number)
    def max(number[::1] a):
        cdef:
            Py_ssize_t i
            number m
        m = a[0]
        for i in range(1, a.shape[0]):
            if a[i] > m:
                m = a[i]
        return m
    """

# Min function for 1D memory views of numbers
if not cython.compiled:
    # Use NumPy's min function in pure Python
    min = np.min
else:
    """
    @cython.header(returns=number)
    def min(number[::1] a):
        cdef:
            Py_ssize_t i
            number m
        m = a[0]
        for i in range(1, a.shape[0]):
            if a[i] < m:
                m = a[i]
        return m
    """

# Modulo function for numbers
@cython.header(x=signed_number,
               length=signed_number2,
               returns=signed_number,
               )
def mod(x, length):
    """Warning: mod(integer, floating) not possible. Note that
    no error will occur if called with illegal types!
    Note also that -length < x < 2*length must be true for this
    function to compute the modulo properly. A more general
    prescription would be x = (x % length) + (x < 0)*length.
    """
    if not (signed_number in integer and signed_number2 in floating):
        if x < 0:
            x += length
        elif x >= length:
            x -= length
        return x

# Summation function for 1D memory views of numbers
if not cython.compiled:
    # Use NumPy's sum function in pure Python
    sum = np.sum
else:
    """
    @cython.header(returns=number)
    def sum(number[::1] a):
        cdef:
            number Σ
            Py_ssize_t N
            Py_ssize_t i
        N = a.shape[0]
        if N == 0:
            return 0
        Σ = a[0]
        for i in range(1, N):
            Σ += a[i]
        return Σ
    """

# Product function for 1D memory views of numbers
if not cython.compiled:
    # Use NumPy's prod function in pure Python
    prod = np.prod
else:
    """
    @cython.header(returns=number)
    def prod(number[::1] a):
        cdef:
            number Π
            Py_ssize_t N
            Py_ssize_t i
        N = a.shape[0]
        if N == 0:
            return 1
        Π = a[0]
        for i in range(1, N):
            Π *= a[i]
        return Π
    """

# Unnormalized sinc function (faster than gsl_sf_sinc)
@cython.header(x='double',
               y='double',
               returns='double',
               )
def sinc(x):
    y = sin(x)
    if y == x:
        return 1
    else:
        return y/x

# Function for printing messages as well as timed progress messages
def masterprint(msg, *args, indent=0, end='\n', **kwargs):
    global progressprint_time
    if not master:
        return
    if msg == 'done':
        # End of progress message
        interval = timedelta(seconds=(time() - progressprint_time)).__str__()
        if interval.startswith('0:'):
            # Less than an hour
            interval = interval[2:]
            if interval.startswith('00:'):
                # Less than a minute
                interval = interval[3:]
                if interval.startswith('00.'):
                    if interval[3:6] == '000':
                        # Less than a millisecond
                        interval = '< 1 ms'
                    else:
                        # Less than a second
                        interval = interval[3:6].lstrip('0') + ' ms'
                else:
                    # Between a second and a minute
                    if interval.startswith('0'):
                        # Between 1 and 10 seconds
                        if '.' in interval:
                            interval = interval[1:(interval.index('.') + 2)] + ' s'
                    else:
                        # Between 10 seconds and a minute
                        if '.' in interval:
                            interval = interval[:interval.index('.')] + ' s'
            else:
                # Between a minute and an hour
                if interval.startswith('0'):
                    interval = interval[1:]
                if '.' in interval:
                    interval = interval[:interval.index('.')]
        else:
            # More than an hour
            if '.' in interval:
                interval = interval[:interval.index('.')]
        print(' done after ' + interval, *args, flush=True, **kwargs)
    else:
        # Create time stamp for use in progress message
        progressprint_time = time()
        # Print out message
        msg = str(msg).replace('CONCEPT', terminal.CONCEPT)
        args = [arg.replace('CONCEPT', terminal.CONCEPT)
                if isinstance(arg, str) else arg for arg in args]
        if ((args and isinstance(args[-1], str) and args[-1].endswith('...'))
            or not args and msg.endswith('...')):
            end = ''
        print(' '*indent + msg, *args, flush=True, end=end, **kwargs)

# Function for printing warnings
def masterwarn(msg, *args, indent=0, prefix='Warning', **kwargs):
    if not master:
        return
    msg = str(msg).replace('CONCEPT', terminal.CONCEPT)
    if args:
        args = [arg.replace('CONCEPT', terminal.CONCEPT)
                if isinstance(arg, str) else str(arg) for arg in args]
        print(terminal.bold_red(' '*indent + 'Warning: '
                                + ' '.join([msg] + args)),
                                file=sys.stderr,
                                flush=True,
                                **kwargs)
    else:
        print(terminal.bold_red(' '*indent + prefix + ': ' + msg),
              file=sys.stderr,
              flush=True,
              **kwargs)

# This function formats a floating point number to have nfigs
# significant figures. Set fmt to 'LaTeX' to format to LaTeX math code
# (e.g. '1.234\times 10^{-5}') or 'Unicode' to format to superscript
# Unicode (e.g. 1.234×10⁻⁵).
@cython.header(# Arguments
               number='double',
               nfigs='int',
               fmt='str',
               # Locals
               coefficient='str',
               exponent='str',
               n_missing_zeros='int',
               number_str='str',
               returns='str',
               )
def significant_figures(number, nfigs, fmt=''):
    # Format the number using nfigs
    number_str = ('{:.' + str(nfigs) + 'g}').format(number)
    # Handle the exponent
    if 'e' in number_str:
        e_index = number_str.index('e')
        coefficient = number_str[:e_index]
        exponent = number_str[e_index:]
        # Remove superfluous 0 in exponent
        if exponent.startswith('e+0') or exponent.startswith('e-0'):
            exponent = exponent[:2] + exponent[3:]
        # Remove plus sign in exponent
        if exponent.startswith('e+'):
            exponent = 'e' + exponent[2:]
        # Handle formatting
        if fmt.lower() == 'latex':
            exponent = exponent.replace('e', r'\times 10^{') + '}'
        elif fmt.lower() == 'unicode':
            exponent = ''.join([unicode_exponent_fmt[c] for c in exponent])
    else:
        coefficient = number_str
        exponent = ''
    # Pad with zeros in case of too few significant digits
    digits = coefficient.replace('.', '').replace('-', '')
    for i, d in enumerate(digits):
        if d != '0':
            digits = digits[i:]
            break
    n_missing_zeros = nfigs - len(digits)
    if n_missing_zeros > 0:
        if not '.' in coefficient:
            coefficient += '.'
        coefficient += '0'*n_missing_zeros
    number_str = coefficient + exponent
    return number_str
# Dict mapping from ordinary to superscript numbers used in
# the significant_figures function.
cython.declare(unicode_exponent_fmt='dict')
unicode_exponent_fmt = dict(zip('0123456789-e',
                                [unicode(c) for c in('⁰', '¹', '²', '³', '⁴',
                                                     '⁵', '⁶', '⁷', '⁸', '⁹', '⁻')]
                                + [unicode('×') + '10']))
