# Import everything from the commons module. In the .pyx file,
# this line will be replaced by the content of commons.py itself.
from commons import *

# Seperate but equivalent imports in pure Python and Cython
if not cython.compiled:
    from communication import cutout_domains
else:
    # Lines in triple quotes will be executed in the .pyx file
    """
    from communication cimport cutout_domains
    """


# Function for tabulating a cubic grid with vector values
@cython.cfunc
@cython.inline
@cython.boundscheck(False)
@cython.cdivision(True)
@cython.initializedcheck(False)
@cython.wraparound(False)
@cython.locals(# Arguments
               gridsize='int',
               func='func_ddd_ddd',
               factor='double',
               filename='str',
               # Locals
               dim='size_t',
               grid='double[:, :, :, ::1]',
               grid_local='double[:, :, :, ::1]',
               i='size_t',
               i_end='size_t',
               i_start='size_t',
               j='size_t',
               j_end='size_t',
               j_start='size_t',
               k='size_t',
               k_end='size_t',
               k_start='size_t',
               shape='tuple',
               )
@cython.returns('double[:, :, :, ::1]')
def tabulate_vectorfield(gridsize, func, factor, filename):
    """ This function tabulates a cubic grid of size
    gridsize*gridsize*gridsize with vector values computed by the
    function func, as grid[i, j, k] = func(i*factor, j*factor, k*factor).
    The tabulated grid is saved to a hdf5 file named filename.
    """

    # Initialize the grid to be of shape gridsize*gridsize*gridsize*3.
    # That is, grid is not really cubic, but rather four-dimensional.
    shape = (gridsize, )*3 + (3, )
    grid = empty(shape)
    # Each process tabulate its part of the grid
    (i_start, j_start, k_start), (i_end, j_end, k_end) = partition(shape[:3])
    grid_local = empty([i_end - i_start,
                        j_end - j_start,
                        k_end - k_start] + [3])
    for i in range(i_start, i_end):
        for j in range(j_start, j_end):
            for k in range(k_start, k_end):
                # Compute the vector values via the passed function
                vector = func(i*factor, j*factor, k*factor)
                for dim in range(3):
                    grid_local[i - i_start,
                               j - j_start,
                               k - k_start, dim] = vector[dim]
    # Save grid to disk using parallel hdf5
    with h5py.File(filename, mode='w', driver='mpio', comm=comm) as hdf5_file:
        dset = hdf5_file.create_dataset('data', shape, dtype='float64')
        dset[i_start:i_end, j_start:j_end, k_start:k_end, :] = grid_local
    # Every process gets to know the entire grid
    Allgather(grid_local, grid)
    return grid


# Function for doing lookup in a cubic grid with vector values and
# CIC-interpolating to specified coordinates
@cython.cfunc
@cython.inline
@cython.boundscheck(False)
@cython.cdivision(True)
@cython.initializedcheck(False)
@cython.wraparound(False)
@cython.locals(# Argument
               grid='double[:, :, :, ::1]',
               x='double',
               y='double',
               z='double',
               # Locals
               Wxl='double',
               Wxu='double',
               Wyl='double',
               Wyu='double',
               Wzl='double',
               Wzu='double',
               dim='size_t',
               gridsize_minus_1='int',
               x_lower='size_t',
               x_upper='size_t',
               y_lower='size_t',
               y_upper='size_t',
               z_lower='size_t',
               z_upper='size_t',
               )
@cython.returns('double*')
def CIC_grid2coordinates_vector(grid, x, y, z):
    """This function look up tabulated vectors in a cubic grid and interpolates 
    to (x, y, z) via the cloud in cell (CIC) method. Input arguments must be
    normalized so that 0 <= x, y, z < 1. If x, y or z is exactly equal to 1,
    they will be corrected to 1 - ϵ. It is assumed that the grid is
    nonperiodic.
    """

    # Extract the size of the regular, cubic grid
    gridsize_minus_1 = grid.shape[0] - 1
    # Correct for extreme values in the passed coordinates. This is to catch
    # inputs which are slighly larger than 1 due to numerical errors
    if x >= 1:
        x = 1 - two_machine_ϵ
    if y >= 1:
        y = 1 - two_machine_ϵ
    if z >= 1:
        z = 1 - two_machine_ϵ
    # Scale the coordinates so that 0 <= x, y, z < (gridsize - 1)
    x *= gridsize_minus_1
    y *= gridsize_minus_1
    z *= gridsize_minus_1
    # Indices of the 8 vertices (6 faces) of the grid surrounding (x, y, z)
    x_lower = int(x)
    y_lower = int(y)
    z_lower = int(z)
    x_upper = x_lower + 1
    y_upper = y_lower + 1
    z_upper = z_lower + 1
    # The linear weights according to the CIC rule W = 1 - |dist| if |dist| < 1
    Wxl = x_upper - x  # = 1 - (x - x_lower)
    Wyl = y_upper - y  # = 1 - (y - y_lower)
    Wzl = z_upper - z  # = 1 - (z - z_lower)
    Wxu = x - x_lower  # = 1 - (x_upper - x)
    Wyu = y - y_lower  # = 1 - (y_upper - y)
    Wzu = z - z_lower  # = 1 - (z_upper - z)
    # Assign the weighted grid values to the vector components
    for dim in range(3):
        vector[dim] = ( grid[x_lower, y_lower, z_lower, dim]*Wxl*Wyl*Wzl
                      + grid[x_lower, y_lower, z_upper, dim]*Wxl*Wyl*Wzu
                      + grid[x_lower, y_upper, z_lower, dim]*Wxl*Wyu*Wzl
                      + grid[x_lower, y_upper, z_upper, dim]*Wxl*Wyu*Wzu
                      + grid[x_upper, y_lower, z_lower, dim]*Wxu*Wyl*Wzl
                      + grid[x_upper, y_lower, z_upper, dim]*Wxu*Wyl*Wzu
                      + grid[x_upper, y_upper, z_lower, dim]*Wxu*Wyu*Wzl
                      + grid[x_upper, y_upper, z_upper, dim]*Wxu*Wyu*Wzu)
    return vector

# Function for CIC-interpolating particle coordinates
# to a cubic grid with scalar values.
@cython.cfunc
@cython.inline
@cython.boundscheck(False)
@cython.cdivision(True)
@cython.initializedcheck(False)
@cython.wraparound(False)
@cython.locals(# Argument
               particles='Particles',
               grid='double[:, :, ::1]',
               # Locals
               posx='double*',
               posy='double*',
               posz='double*',
               gridsize_x='int',
               gridsize_y='int',
               gridsize_z='int',
               gridsize_x_minus_1='int',
               gridsize_y_minus_1='int',
               gridsize_z_minus_1='int',
               gridsize_x_minus_1_over_domain_size_x='double',
               gridsize_y_minus_1_over_domain_size_y='double',
               gridsize_z_minus_1_over_domain_size_z='double',
               i='size_t',
               x='double',
               y='double',
               z='double',
               x_lower='int',
               y_lower='int',
               z_lower='int',
               x_upper='int',
               y_upper='int',
               z_upper='int',
               Wxl='double',
               Wyl='double',
               Wzl='double',
               Wxu='double',
               Wyu='double',
               Wzu='double',
               )
def CIC_particles2grid(particles, grid):
    """This function CIC-interpolates particle coordinates to grid storing
    scalar values. The passed grid should be nullified beforehand.
    """
    # Extract variables
    posx = particles.posx
    posy = particles.posy
    posz = particles.posz
    gridsize_x = grid.shape[0]
    gridsize_y = grid.shape[1]
    gridsize_z = grid.shape[2]
    # The conversion factors between comoving length and grid units
    gridsize_x_minus_1 = gridsize_x - 1
    gridsize_y_minus_1 = gridsize_y - 1
    gridsize_z_minus_1 = gridsize_z - 1
    gridsize_x_minus_1_over_domain_size_x = gridsize_x_minus_1/domain_size_x
    gridsize_y_minus_1_over_domain_size_y = gridsize_y_minus_1/domain_size_y
    gridsize_z_minus_1_over_domain_size_z = gridsize_z_minus_1/domain_size_z
    # Interpolate each particle
    for i in range(particles.N_local):
        # Get, translate and scale the coordinates so that
        # 0 <= i < gridsize_i - 1 for i in (x, y, z).
        x = (posx[i] - domain_start_x)*gridsize_x_minus_1_over_domain_size_x
        y = (posy[i] - domain_start_y)*gridsize_y_minus_1_over_domain_size_y
        z = (posz[i] - domain_start_z)*gridsize_z_minus_1_over_domain_size_z
        # Correct for coordinates which are exactly at an upper domain boundary
        if x == gridsize_x_minus_1:
            x -= two_machine_ϵ
        if y == gridsize_y_minus_1:
            y -= two_machine_ϵ
        if z == gridsize_z_minus_1:
            z -= two_machine_ϵ
        # Indices of the 8 vertices (6 faces) of the grid surrounding (x, y, z)
        x_lower = int(x)
        y_lower = int(y)
        z_lower = int(z)
        x_upper = x_lower + 1
        y_upper = y_lower + 1
        z_upper = z_lower + 1
        # The linear weights according to the
        # CIC rule W = 1 - |dist| if |dist| < 1.
        Wxl = x_upper - x  # = 1 - (x - x_lower)
        Wyl = y_upper - y  # = 1 - (y - y_lower)
        Wzl = z_upper - z  # = 1 - (z - z_lower)
        Wxu = x - x_lower  # = 1 - (x_upper - x)
        Wyu = y - y_lower  # = 1 - (y_upper - y)
        Wzu = z - z_lower  # = 1 - (z_upper - z)
        # Assign the weights to the grid points
        grid[x_lower, y_lower, z_lower] += Wxl*Wyl*Wzl
        grid[x_lower, y_lower, z_upper] += Wxl*Wyl*Wzu
        grid[x_lower, y_upper, z_lower] += Wxl*Wyu*Wzl
        grid[x_lower, y_upper, z_upper] += Wxl*Wyu*Wzu
        grid[x_upper, y_lower, z_lower] += Wxu*Wyl*Wzl
        grid[x_upper, y_lower, z_upper] += Wxu*Wyl*Wzu
        grid[x_upper, y_upper, z_lower] += Wxu*Wyu*Wzl
        grid[x_upper, y_upper, z_upper] += Wxu*Wyu*Wzu







# Function for communicating boundary values between processes after a CIC
# interpolation to the grid.
@cython.cfunc
@cython.inline
@cython.boundscheck(False)
@cython.cdivision(True)
@cython.initializedcheck(False)
@cython.wraparound(False)
@cython.locals(# Arguments
               domain_grid='double[:, :, ::1]',
               # Locals
               i='int',
               j='int',
               k='int',
               domain_grid_slice_backward='double[:, ::1]',
               domain_grid_slice_backwarddown='double[:]',
               domain_grid_slice_down='double[:, :]',
               domain_grid_slice_forward='double[:, ::1]',
               domain_grid_slice_forwardup='double[:]',
               domain_grid_slice_left='double[:, ::1]',
               domain_grid_slice_leftbackward='double[::1]',
               domain_grid_slice_leftdown='double[:]',
               domain_grid_slice_right='double[:, ::1]',
               domain_grid_slice_rightup='double[:]',
               domain_grid_slice_rightforward='double[::1]',
               domain_grid_slice_up='double[:, :]',
               )
def communicate_domain_grid(domain_grid):
    """The upper three surfaces (right, forward, up) of domain_grid as well as
    the upper three edges (right forward, right upward, forward upward) and
    the right, forward, upward point need to be communicated.
    """
    global sendbuf_faceij, sendbuf_faceik, sendbuf_facejk
    global recvbuf_faceij, recvbuf_faceik, recvbuf_facejk
    global sendbuf_edge, recvbuf_edge
    # 2D slices (contiguous and noncontiguous) of the domain grid
    domain_grid_slice_right = domain_grid[domain_size_i, :, :]
    domain_grid_slice_left = domain_grid[0, :, :]
    domain_grid_slice_forward = domain_grid[:, domain_size_j, :]
    domain_grid_slice_backward = domain_grid[:, 0, :]
    domain_grid_slice_up = domain_grid[:, :, domain_size_k]
    domain_grid_slice_down = domain_grid[:, :, 0]
    # 1D slices (contiguous and noncontiguous) of the domain grid
    domain_grid_slice_rightforward = domain_grid[domain_size_i, domain_size_j, :]
    domain_grid_slice_leftbackward = domain_grid[0, 0, :]
    domain_grid_slice_rightup = domain_grid[domain_size_i, :, domain_size_k]
    domain_grid_slice_leftdown = domain_grid[0, :, 0]
    domain_grid_slice_forwardup = domain_grid[:, domain_size_j, domain_size_k]
    domain_grid_slice_backwarddown = domain_grid[:, 0, 0]
    # Cummunicate the right face
    for j in range(domain_size_j):
        for k in range(domain_size_k):
            sendbuf_facejk[j, k] = domain_grid_slice_right[j, k]
    Sendrecv(sendbuf_facejk, dest=rank_right, recvbuf=recvbuf_facejk,
             source=rank_left)
    # Add the received contribution to the left face
    for j in range(domain_size_j):
        for k in range(domain_size_k):
            domain_grid_slice_left[j, k] += recvbuf_facejk[j, k]
    # Cummunicate the forward face
    for i in range(domain_size_i):
        for k in range(domain_size_k):
            sendbuf_faceik[i, k] = domain_grid_slice_forward[i, k]
    Sendrecv(sendbuf_faceik, dest=rank_forward, recvbuf=recvbuf_faceik,
             source=rank_backward)
    # Add the received contribution to the backward face
    for i in range(domain_size_i):
        for k in range(domain_size_k):
            domain_grid_slice_backward[i, k] += recvbuf_faceik[i, k]
    # Cummunicate the upward face
    for i in range(domain_size_i):
        for j in range(domain_size_j):
            sendbuf_faceij[i, j] = domain_grid_slice_up[i, j]
    Sendrecv(sendbuf_faceij, dest=rank_up, recvbuf=recvbuf_faceij,
             source=rank_down)
    # Add the received contribution to the lower face
    for i in range(domain_size_i):
        for j in range(domain_size_j):
            domain_grid_slice_down[i, j] += recvbuf_faceij[i, j]
    # Communicate the right, forward edge
    for k in range(domain_size_k):
        sendbuf_edge[k] = domain_grid_slice_rightforward[k]
    Sendrecv(sendbuf_edge[:domain_size_k], dest=rank_rightforward,
             recvbuf=recvbuf_edge, source=rank_leftbackward)
    # Add the received contribution to the left, backward edge
    for k in range(domain_size_k):
        domain_grid_slice_leftbackward[k] += recvbuf_edge[k]
    # Communicate the right, upward edge
    for j in range(domain_size_j):
        sendbuf_edge[j] = domain_grid_slice_rightup[j]
    Sendrecv(sendbuf_edge[:domain_size_j], dest=rank_rightup, recvbuf=recvbuf_edge,
             source=rank_leftdown)
    # Add the received contribution to the left, downward edge
    for j in range(domain_size_j):
        domain_grid_slice_leftdown[j] += recvbuf_edge[j]
    # Communicate the forward, upward edge
    for i in range(domain_size_i):
        sendbuf_edge[i] = domain_grid_slice_forwardup[i]
    Sendrecv(sendbuf_edge[:domain_size_i], dest=rank_forwardup, recvbuf=recvbuf_edge,
             source=rank_backwarddown)
    # Add the received contribution to the backward, downward edge
    for i in range(domain_size_i):
        domain_grid_slice_backwarddown[i] += recvbuf_edge[i]
    # Communicate the right, forward, upward point
    domain_grid[0, 0, 0] += sendrecv(domain_grid[domain_size_i,
                                                 domain_size_j,
                                                 domain_size_k],
                                     dest=rank_rightforwardup,
                                     source=rank_leftbackwarddown)

# Function for transfering the interpolated data
# in the domain grid to the PM grid.
@cython.cfunc
@cython.inline
@cython.boundscheck(False)
@cython.cdivision(True)
@cython.initializedcheck(False)
@cython.wraparound(False)
@cython.locals(# Arguments
               domain_grid='double[:, :, ::1]',
               PM_grid='double[:, :, ::1]',
               # Locals
               ID_send='int',
               ID_recv='int',
               i='int',
               j='int',
               k='int',
               ℓ='int',
               )
def domain2PM(domain_grid, PM_grid):
    # Communicate the interpolated domain grid to the PM grid
    for ℓ in range(ℓmax):
        # Send part of the local domain grid to the corresponding process
        if ℓ < PM_send_rank.shape[0]:
            ID_send = PM_send_rank[ℓ]
            for i in range(PM_send_i_start[ℓ], PM_send_i_end[ℓ]):
                for j in range(domain_size_j):
                    for k in range(domain_size_k):
                        domainPM_sendbuf[i - PM_send_i_start[ℓ], j, k] = domain_grid[i, j, k]
            Send(domainPM_sendbuf, dest=ID_send)
        # The lower ranks storing the PM mesh reveives the message
        if ℓ < PM_recv_rank.shape[0]:
            ID_recv = PM_recv_rank[ℓ]
            Recv(domainPM_recvbuf, source=ID_recv)
            for i in range(PM_recv_i_start[ℓ], PM_recv_i_end[ℓ]):
                for j in range(PM_recv_j_start[ℓ], PM_recv_j_end[ℓ]):
                    for k in range(PM_recv_k_start[ℓ], PM_recv_k_end[ℓ]):
                        PM_grid[i, j, k] = domainPM_recvbuf[i, j - PM_recv_j_start[ℓ], k - PM_recv_k_start[ℓ]]


if use_PM:
    # Information about the domain used in the communicate_domain_grid function
    cython.declare(domain_cuts='int[::1]',
                   domain_layout='int[:, :, ::1]',
                   domain_local='int[::1]',
                   domain_size_x='double',
                   domain_size_y='double',
                   domain_size_z='double',
                   domain_start_x='double',
                   domain_start_y='double',
                   domain_start_z='double',
                   domain_end_x='double',
                   domain_end_y='double',
                   domain_end_z='double',
                   domain_size_i='int',
                   domain_size_j='int',
                   domain_size_k='int',
                   rank_right='int',
                   rank_left='int',
                   rank_forward='int',
                   rank_backward='int',
                   rank_up='int',
                   rank_down='int',
                   rank_rightforward='int',
                   rank_leftbackward='int',
                   rank_rightup='int',
                   rank_leftdown='int',
                   rank_forwardup='int',
                   rank_backwarddown='int',
                   rank_rightforwardup='int',
                   rank_leftbackwarddown='int',
                   recvbuf_edge='double[::1]',
                   recvbuf_faceij='double[:, ::1]',
                   recvbuf_faceik='double[:, ::1]',
                   recvbuf_facejk='double[:, ::1]',
                   sendbuf_edge='double[::1]',
                   sendbuf_faceij='double[:, ::1]',
                   sendbuf_faceik='double[:, ::1]',
                   sendbuf_facejk='double[:, ::1]',
                   )
    # Number of domains in all three dimensions
    domain_cuts = array(cutout_domains(nprocs), dtype='int32')
    # The 3D layout of the division of the box
    domain_layout = arange(nprocs, dtype='int32').reshape(domain_cuts)
    # The indices in domain_layout of the local domain
    domain_local = array(np.unravel_index(rank, domain_cuts), dtype='int32')
    # The linear size of the domains, which are the same for all of them
    domain_size_x = boxsize/domain_cuts[0]
    domain_size_y = boxsize/domain_cuts[1]
    domain_size_z = boxsize/domain_cuts[2]
    # The start and end positions of the local domain
    domain_start_x = domain_local[0]*domain_size_x
    domain_start_y = domain_local[1]*domain_size_y
    domain_start_z = domain_local[2]*domain_size_z
    domain_end_x = domain_start_x + domain_size_x
    domain_end_y = domain_start_x + domain_size_x
    domain_end_z = domain_start_x + domain_size_x

    # Get the ranks of the 6 neighboring processes
    rank_right = domain_layout[mod(domain_local[0] + 1, domain_cuts[0]),
                               domain_local[1],
                               domain_local[2]]
    rank_left = domain_layout[mod(domain_local[0] - 1, domain_cuts[0]),
                               domain_local[1],
                               domain_local[2]]
    rank_forward = domain_layout[domain_local[0],
                                 mod(domain_local[1] + 1, domain_cuts[1]),
                                 domain_local[2]]
    rank_backward = domain_layout[domain_local[0],
                                  mod(domain_local[1] - 1, domain_cuts[1]),
                                  domain_local[2]]
    rank_up = domain_layout[domain_local[0],
                            domain_local[1],
                            mod(domain_local[2] + 1, domain_cuts[2])]
    rank_down = domain_layout[domain_local[0],
                              domain_local[1],
                              mod(domain_local[2] - 1, domain_cuts[2])]
    # Now get the ranks of the 6 diagonal neighboring processes
    rank_rightforward = domain_layout[mod(domain_local[0] + 1, domain_cuts[0]),
                                      mod(domain_local[1] + 1, domain_cuts[1]),
                                      domain_local[2]]
    rank_leftbackward = domain_layout[mod(domain_local[0] - 1, domain_cuts[0]),
                                      mod(domain_local[1] - 1, domain_cuts[1]),
                                      domain_local[2]]
    rank_rightup = domain_layout[mod(domain_local[0] + 1, domain_cuts[0]),
                                 domain_local[1],
                                 mod(domain_local[2] + 1, domain_cuts[2])]
    rank_leftdown = domain_layout[mod(domain_local[0] - 1, domain_cuts[0]),
                                  domain_local[1],
                                  mod(domain_local[2] - 1, domain_cuts[2])]
    rank_forwardup = domain_layout[domain_local[0],
                                   mod(domain_local[1] + 1, domain_cuts[1]),
                                   mod(domain_local[2] + 1, domain_cuts[2])]
    rank_backwarddown = domain_layout[domain_local[0],
                                      mod(domain_local[1] - 1, domain_cuts[1]),
                                      mod(domain_local[2] - 1, domain_cuts[2])]
    # Finally get the ranks of the two 3D-diagonal neighboring processes
    rank_rightforwardup = domain_layout[mod(domain_local[0] + 1,
                                            domain_cuts[0]),
                                        mod(domain_local[1] + 1,
                                            domain_cuts[1]),
                                        mod(domain_local[2] + 1,
                                            domain_cuts[2])]
    rank_leftbackwarddown = domain_layout[mod(domain_local[0] - 1,
                                              domain_cuts[0]),
                                          mod(domain_local[1] - 1,
                                              domain_cuts[1]),
                                          mod(domain_local[2] - 1,
                                              domain_cuts[2])]
    # The actual size of the domain grid. This is 1 less than the allocated
    # size in each dimension, as the last element is actually the first element
    # of the domain on some other process.
    domain_size_i = PM_gridsize//domain_cuts[0]
    domain_size_j = PM_gridsize//domain_cuts[1]
    domain_size_k = PM_gridsize//domain_cuts[2]
    # Send/recieve buffers.
    # Separate buffers for each face is needed to ensure contiguousity. 
    sendbuf_faceij = empty((domain_size_i, domain_size_j), dtype='float64')
    recvbuf_faceij = empty((domain_size_i, domain_size_j), dtype='float64')
    sendbuf_faceik = empty((domain_size_i, domain_size_k), dtype='float64')
    recvbuf_faceik = empty((domain_size_i, domain_size_k), dtype='float64')
    sendbuf_facejk = empty((domain_size_j, domain_size_k), dtype='float64')
    recvbuf_facejk = empty((domain_size_j, domain_size_k), dtype='float64')
    sendbuf_edge = empty(np.max((domain_size_i, domain_size_j, domain_size_k)), dtype='float64')
    recvbuf_edge = empty(np.max((domain_size_i, domain_size_j, domain_size_k)), dtype='float64')

    # Additional information about the domain grid and the PM mesh,
    # used in the domain2PM function.
    cython.declare(ID_recv='int',
                   ID_send='int',
                   PM_gridsize_local_i='int',
                   PM_gridsize_global_i='int',
                   PM_send_i_end='int[::1]',
                   PM_send_i_end_list='list',
                   PM_send_i_start='int[::1]',
                   PM_send_i_start_list='list',
                   PM_send_rank='int[::1]',
                   PM_send_rank_list='list',
                   PM_recv_i_start='int[::1]',
                   PM_recv_i_start_list='list',
                   PM_recv_j_start='int[::1]',
                   PM_recv_j_start_list='list',
                   PM_recv_k_start='int[::1]',
                   PM_recv_k_start_list='list',
                   PM_recv_i_end='int[::1]',
                   PM_recv_i_end_list='list',
                   PM_recv_j_end='int[::1]',
                   PM_recv_j_end_list='list',
                   PM_recv_k_end='int[::1]',
                   PM_recv_k_end_list='list',
                   PM_recv_rank='int[::1]',
                   PM_recv_rank_list='list',
                   domain_start_i='int',
                   domain_start_j='int',
                   domain_start_k='int',
                   domain_end_i='int',
                   domain_end_j='int',
                   domain_end_k='int',
                   domainPM_sendbuf='double[:, :, ::1]',
                   domainPM_recvbuf='double[:, :, ::1]',
                   ℓ='int',
                   ℓmax='int',
                   )
    # The global start and end indices of the local domain in the total PM_grid
    domain_start_i = domain_local[0]*domain_size_i
    domain_start_j = domain_local[1]*domain_size_j
    domain_start_k = domain_local[2]*domain_size_k
    domain_end_i = domain_start_i + domain_size_i
    domain_end_j = domain_start_j + domain_size_j
    domain_end_k = domain_start_k + domain_size_k
    # PM_gridsize_local_i is the same for all processes participating in the PM
    # algorithm and 0 otherwise. The global version is equal to the nonzero
    # value on all processes.
    PM_gridsize_local_i = PM_gridsize//nprocs
    if rank < PM_gridsize and PM_gridsize_local_i == 0:
        PM_gridsize_local_i = 1      
    PM_gridsize_global_i = PM_gridsize_local_i
    if PM_gridsize_global_i == 0:
        PM_gridsize_global_i = 1
    # Find local i-indices to send and to which process
    PM_send_i_start_list = []
    PM_send_i_end_list = []
    PM_send_rank_list = []
    for ℓ in range(domain_start_i, domain_end_i, PM_gridsize_global_i):
        PM_send_i_start_list.append(ℓ - domain_start_i)
        PM_send_i_end_list.append(ℓ - domain_start_i + PM_gridsize_global_i)
        PM_send_rank_list.append(ℓ//PM_gridsize_global_i)
    # Shift the elements so that they match the communication pattern used
    PM_send_i_start_list = list(np.roll(PM_send_i_start_list, -rank))
    PM_send_i_end_list = list(np.roll(PM_send_i_end_list, -rank))
    PM_send_rank_list = list(np.roll(PM_send_rank_list, -rank))
    # Communicate the start and end (j, k)-indices of the PM grid, where
    # future parts of the local domains should be received into.
    PM_recv_i_start_list = []
    PM_recv_j_start_list = []
    PM_recv_k_start_list = []
    PM_recv_i_end_list = []
    PM_recv_j_end_list = []
    PM_recv_k_end_list = []
    PM_recv_rank_list = []
    for ℓ in range(nprocs):
        # Process ranks to send/recieve to/from
        ID_send = mod(rank + ℓ, nprocs)
        ID_recv = mod(rank - ℓ, nprocs)
        # Send the global y and z start and end indices of the region to be
        # send, if anything should be send to process ID_send.
        # Otherwize send None.      
        sendbuf = (domain_start_j,
                   domain_start_k,
                   domain_end_j,
                   domain_end_k) if ID_send in PM_send_rank_list else None
        recvbuf = sendrecv(sendbuf, dest=ID_send, source=ID_recv)
        if recvbuf is not None:
            PM_recv_i_start_list.append(0)
            PM_recv_i_end_list.append(PM_gridsize_local_i)
            PM_recv_j_start_list.append(recvbuf[0])
            PM_recv_k_start_list.append(recvbuf[1])
            PM_recv_j_end_list.append(recvbuf[2])
            PM_recv_k_end_list.append(recvbuf[3])
            PM_recv_rank_list.append(ID_recv)
    # Memoryview versions of the lists
    PM_send_i_start = array(PM_send_i_start_list, dtype='int32')
    PM_send_i_end = array(PM_send_i_end_list, dtype='int32')
    PM_send_rank = array(PM_send_rank_list, dtype='int32')
    PM_recv_i_start = array(PM_recv_i_start_list, dtype='int32')
    PM_recv_j_start = array(PM_recv_j_start_list, dtype='int32')
    PM_recv_k_start = array(PM_recv_k_start_list, dtype='int32')
    PM_recv_i_end = array(PM_recv_i_end_list, dtype='int32')
    PM_recv_j_end = array(PM_recv_j_end_list, dtype='int32')
    PM_recv_k_end = array(PM_recv_k_end_list, dtype='int32')
    PM_recv_rank = array(PM_recv_rank_list, dtype='int32')
    # Buffers
    domainPM_sendbuf = empty((PM_gridsize_global_i, domain_size_j, domain_size_k), dtype='float64')
    if PM_recv_rank_list != []:
        domainPM_recvbuf = empty((PM_gridsize_global_i, domain_size_j, domain_size_k), dtype='float64')
    # ℓ will be the communication loop index. It runs from 0 t0 ℓmax - 1
    ℓmax = np.max([PM_send_rank.shape[0], PM_recv_rank.shape[0]])



