# This file is part of CONCEPT, the cosmological N-body code in Python.
# Copyright (C) 2015 Jeppe Mosgard Dakin.
#
# CONCEPT is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# CONCEPT is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with CONCEPT. If not, see http://www.gnu.org/licenses/
#
# The auther of CONCEPT can be contacted at
# jeppe.mosgaard.dakin(at)post.au.dk
# The latest version of CONCEPT is available at
# https://github.com/jmd-dk/concept/



# This file has to be run in pure Python mode!

# Include the concept_dir in the searched paths
import sys, os
sys.path.append(os.environ['concept_dir'])

# Imports from the CONCEPT code
from commons import *
from species import construct
from IO import save

# Create the particles.
# It is important that no interparticle separation exceeds boxsize/2 in
# any direction, as the nearest particle image in all cases must be the
# actual particle itself.
N = 8
mass = Ωm*ϱ*boxsize**3/N
particles = construct('kick_without_Ewald test', 'dark matter', mass, N)
particles.populate(array([0.26]*4 + [0.74]*4)*boxsize, 'posx')
particles.populate(array([0.25, 0.25, 0.75, 0.75]*2)*boxsize, 'posy')
particles.populate(array([0.25, 0.75, 0.75, 0.25]*2)*boxsize, 'posz')
particles.populate(zeros(N), 'momx')
particles.populate(zeros(N), 'momy')
particles.populate(zeros(N), 'momz')

# Save snapshot
save(particles, a_begin, IC_file)

