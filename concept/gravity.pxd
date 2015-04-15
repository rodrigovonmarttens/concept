from species cimport Particles

cdef:
    direct_summation(double* posx_i, double* posy_i, double* posz_i, double* momx_i, double* momy_i, double* momz_i, double mass_i, size_t N_local_i, double* posx_j, double* posy_j, double* posz_j, double* __ASCII_repr_of_unicode__greek_Deltamomx_j, double* __ASCII_repr_of_unicode__greek_Deltamomy_j, double* __ASCII_repr_of_unicode__greek_Deltamomz_j, double mass_j, size_t N_local_j, double __ASCII_repr_of_unicode__greek_Deltat, double softening2, bint only_short_range, int flag_input=*)
    PP(Particles particles, double __ASCII_repr_of_unicode__greek_Deltat, bint only_short_range=*)
    PM_update_mom(size_t N_local, double PM_fac, double[:,:,::1] force_grid, double* posx, double* posy, double* posz, double* mom)
    PM(Particles particles, double __ASCII_repr_of_unicode__greek_Deltat, bint only_long_range=*)
    bint in_boundary_right(double posx_local_i, double posy_local_i, double posz_local_i)
    bint in_boundary_left(double posx_local_i, double posy_local_i, double posz_local_i)
    bint in_boundary_forward(double posx_local_i, double posy_local_i, double posz_local_i)
    bint in_boundary_backward(double posx_local_i, double posy_local_i, double posz_local_i)
    bint in_boundary_up(double posx_local_i, double posy_local_i, double posz_local_i)
    bint in_boundary_down(double posx_local_i, double posy_local_i, double posz_local_i)
    bint in_boundary_rightforward(double posx_local_i, double posy_local_i, double posz_local_i)
    bint in_boundary_rightbackward(double posx_local_i, double posy_local_i, double posz_local_i)
    bint in_boundary_rightup(double posx_local_i, double posy_local_i, double posz_local_i)
    bint in_boundary_rightdown(double posx_local_i, double posy_local_i, double posz_local_i)
    bint in_boundary_leftforward(double posx_local_i, double posy_local_i, double posz_local_i)
    bint in_boundary_leftbackward(double posx_local_i, double posy_local_i, double posz_local_i)
    bint in_boundary_leftup(double posx_local_i, double posy_local_i, double posz_local_i)
    bint in_boundary_leftdown(double posx_local_i, double posy_local_i, double posz_local_i)
    bint in_boundary_forwardup(double posx_local_i, double posy_local_i, double posz_local_i)
    bint in_boundary_forwarddown(double posx_local_i, double posy_local_i, double posz_local_i)
    bint in_boundary_backwardup(double posx_local_i, double posy_local_i, double posz_local_i)
    bint in_boundary_backwarddown(double posx_local_i, double posy_local_i, double posz_local_i)
    bint in_boundary_rightforwardup(double posx_local_i, double posy_local_i, double posz_local_i)
    bint in_boundary_rightforwarddown(double posx_local_i, double posy_local_i, double posz_local_i)
    bint in_boundary_rightbackwardup(double posx_local_i, double posy_local_i, double posz_local_i)
    bint in_boundary_rightbackwarddown(double posx_local_i, double posy_local_i, double posz_local_i)
    bint in_boundary_leftforwardup(double posx_local_i, double posy_local_i, double posz_local_i)
    bint in_boundary_leftforwarddown(double posx_local_i, double posy_local_i, double posz_local_i)
    bint in_boundary_leftbackwardup(double posx_local_i, double posy_local_i, double posz_local_i)
    bint in_boundary_leftbackwarddown(double posx_local_i, double posy_local_i, double posz_local_i)
    P3M(Particles particles, double __ASCII_repr_of_unicode__greek_Deltat)
