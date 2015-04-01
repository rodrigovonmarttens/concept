ctypedef double* (*func_ddd_ddd_pxd)(double, double, double)
cdef double[:, :, :, ::1] tabulate_vectorfield(int gridsize, func_ddd_ddd_pxd func, double factor, str filename)

cdef double* CIC_grid2coordinates_vector(double[:, :, :, ::1] grid, double x, double y, double z)

from species cimport Particles
cdef  CIC_particles2grid(Particles particle, double[:, :, ::1] grid)

cdef communicate_domain_grid(double[:, :, ::1] domain_grid)

cdef domain2PM(double[:, :, ::1] domain_grid, double[:, :, ::1] PM_grid)
