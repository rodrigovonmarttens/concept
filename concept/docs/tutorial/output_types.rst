Other kinds of output
---------------------
So far, the result of any simulation has been power spectra, though several
other types of output are available, as examplified by the below parameter
file:

.. code-block:: python3

   # Non-parameter variable used to control the size of the simulation
   _size = 64

   # Input/output
   initial_conditions = {
       'name'   : 'matter component',
       'species': 'matter particles',
       'N'      : _size**3,
   }
   output_dirs = {
       'snapshot' : paths['output_dir'] + '/' + basename(paths['params']),
       'powerspec': ...,
       'render2D' : ...,
       'render3D' : ...,
   }
   output_times = {
       'snapshot' : 0.5,
       'powerspec': [a_begin, 1],
       'render3D' : ...,
       'render2D' : logspace(log10(a_begin), log10(1), 15),
   }
   powerspec_select = {
       'matter component': {'data': True, 'plot': False},
   }
   render2D_select = {
       'matter component': {'data': False, 'image': True,  'terminal image': True},
   }

   # Numerical parameters
   boxsize = 128*Mpc
   φ_gridsize = 2*_size

   # Cosmology
   H0      = 67*km/(s*Mpc)
   Ωcdm    = 0.27
   Ωb      = 0.049
   a_begin = 0.02

   # Physics
   select_forces = {'all': {'gravity': 'p3m'}}

   # Graphics
   render2D_options = {
       'terminal resolution': {
           'matter component': min(φ_gridsize, 80),
       },
       'colormap': {
           'matter component': 'inferno',
       },
   }
   render3D_colors = {
       'matter component': 'lime',
   }
   render3D_bgcolor    = 'black'
   render3D_resolution = 640

Run a simulation using these parameters, e.g. by saving them to
``params/tutorial`` and execute

.. code-block:: bash

   ./concept -p params/tutorial -n 4

This will take a few minutes. You may read along in the meantime.

We see that besides power spectra, we have *snapshots* and *renders*, the
latter of which comes in a 2D and a 3D version. The ellipses (``...``) used
above in ``output_dirs`` indicates that we want all kinds of output to go to
the same directory.

For the ``output_times``, different values are given for three of the output
types, while ``'render3D'`` is set to use the same times as the output just
above it, i.e. that of ``'powerspec'``. For ``'render2D'``, we've specified 15
outputs logarithmically spaced between :math:`a=a_{\mathrm{begin}}=0.02` and
:math:`a=1`.

Among the new parameters introduced are ``powerspec_select``, in which we have
specified that we only want the data files as output, not a plot of this data.



3D renders
..........
Looking in the output directory, among other things you'll find image files
with names starting with ``render3D``. These are --- unsurprisingly --- the 3D
renders. The colors are controlled through the ``render3D_colors`` and
``render3D_bgcolor`` parameters, while the (square) size (in pixels) is set by
``render3D_resolution``. All particles of a given component gets the same
color, though different colors may be used for different components when
running such simulations. The brightness of each pixel indicate the local
energy density.

The colors used (here ``'lime'`` and ``'black'``) may be any color recognized
by `matplotlib <https://matplotlib.org/>`_. A list of named colors is available
`here <https://matplotlib.org/3.1.1/gallery/color/named_colors.html>`_.
Alternatively, you may pass a 3-tuple, e.g. ``render3D_bgcolor = (1, 0, 0)``
makes the background red.



2D renders
..........
The 2D renders show the particle configuration projected along one of the axes
of the box. These can often be prettier than their 3D counterparts, as a
colormap is used to visualise the density field, rather than just a single
color combined with alpha compositing.

In the ``render2D_select`` parameter we've specified that we want images as
well as terminal images, but no data. Here, *images* refer to the 2D render
image files you see in the output directory. *Terminal images* are rendered in
the terminal as part of the printed output, as you probably noticed when
running the simulation. If the colors in the terminal renders does not look
like those in the image files, refer to the first note on
:doc:`this <first_simulations>` page. If you turn on the *data* output, the 2D
render data will be stored in a HDF5 file, handy for further processing (e.g.
for making a small animation).

The options for the 2D renders are collected in the ``render2D_options``
parameter. The resolution (width in characters) of the terminal images is set
to be the smallest of ``φ_gridsize`` and ``80``. This is a reasonable choice,
as the :math:`\varphi` grid is reused to do the particle projection, and so
the actual resolution is set by ``φ_gridsize``. At the same time however, we
don't want the terminal image to be larger than our (terminal emulator) screen,
which is almost always at least 80 characters in width. The resolution of the
image files are always equal to ``φ_gridsize``.

Also available through ``render2D_options`` is the colormap to use. Check out
`this <https://matplotlib.org/3.1.1/gallery/color/colormap_reference.html>`_
for a list of available colormaps.


.. topic:: The play utility

   For this next trick, the simulation need to have finished, and we need to
   know its job ID.

   .. tip::
      You can get the job ID from the header of any of the produced
      power spectra, e.g.

      .. code-block:: bash

         grep -o 'job [^ ]*' output/tutorial/powerspec_a=0.02

   With the job ID at hand, try the following:

   .. code-block:: bash

      ./concept -u play <ID>  # replace <ID> with job ID number

   You should see a nice animation of the evolution of the large-scale
   structure, playing out right in the terminal (does it get any better?). The
   animation is produced from the terminal images stored in the log file
   ``logs/<ID>``. The ``-u`` option to the ``concept`` script signals
   CO\ *N*\ CEPT to start up a *utility* rather than running a simulation.
   These utilities are handy (or perhaps goofy) side programs baked into
   CO\ *N*\ CEPT.



Snapshots
.........
Snapshots are raw dumps of the total system, in this case the position and
momenta of all :math:`64^3` particles. CO\ *N*\ CEPT uses its own snapshot
format, which is simply a well-structured HDF5 file.

.. tip::
   For a great graphical tool to explore HDF5 files in general, check out
   `ViTables <http://vitables.org/>`_. If you encounter problems viewing HDF5
   files produced by CO\ *N*\ CEPT, try upgrading to ViTables 3.

Such snapshots are useful if you want to process the raw data using some
external program. You can also initialize a simulation from a snapshot, instead
of generating initial conditions from scratch. To try this, redefine the
initial conditions to simply be the path to the produced snapshot:

.. code-block:: python3

   initial_conditions = 'output/tutorial/snapshot_a=0.50.hdf5'

Also, you should change ``a_begin`` to be ``0.5`` as to comply with the time at
which the snapshot was dumped. Finally, before rerunning the simulation
starting from the snapshot, you should probably comment out at least the
``'render2D'`` ``output_times``, as to not clutter up the output directory too
heavily.

If you forget to correct ``a_begin``, a warning will be emitted. The same goes
for other obvious inconsistencies between the parameter file and the snapshot,
like if ``boxsize`` or ``Ωcdm`` is wrong. To be able to do this, some meta data
about the cosmology and numerical setup is stored in the snapshot as well.

If you intend to run many simulations using the same initial conditions, it's
worthwhile to initialize these from a common snapshot, as it saves computation
time in the beginning of the simulation, and also takes up less memory. To
produce such an initial snapshot, simply set
``output_times = {'snapshot': a_begin}``, in which case CO\ *N*\ CEPT will
exit right after the snapshot has been dumped at the initial time, without
doing any simulation. Also, the whole purpose of having the ``ICs`` directory
is to hold such initial condition snapshots. To dump snapshots to this
directory, use ``output_dirs = {'snapshot': paths['ics_dir']}``.

You may also want to use CO\ *N*\ CEPT purely as an initial condition
generator, and perform the actual simulation using some other code. If so, the
standard CO\ *N*\ CEPT snapshot format is of little use. To this end,
CO\ *N*\ CEPT also supports the binary Fortran format of
`GADGET-2 <https://wwwmpa.mpa-garching.mpg.de/gadget/>`_, specifically the
*second* type (``SnapFormat = 2`` in GADGET-2), which is arguably harder to
read but understood by several other simulation codes and tools. To use this
snapshot format in place of the standard one, add
``snapshot_type = 'gadget2'`` to your parameter file.


.. topic:: The info utility

   We mentioned `ViTables <http://vitables.org/>`_ as a great way to peek
   inside the default CO\ *N*\ CEPT (HDF5) snapshots. It would be nice to have
   a general tool which worked for the supported GADGET-2 snapshots as well.
   Luckily, CO\ *N*\ CEPT comes with just such a tool: the *info utility*.
   To try it out, simply do

   .. code-block:: bash

      ./concept -u info output/tutorial

   The content of all snapshots --- standard (HDF5) or GADGET-2 format --- in
   the ``output/tutorial`` directory will now be printed to the screen. Should
   you want information about just a specific snapshot, simply provide its
   entire path.





