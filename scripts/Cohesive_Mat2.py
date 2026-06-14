# -*- coding: utf-8 -*-
"""Create Abaqus sets for potential transverse crack paths.

This script groups the partition edges where cohesive elements/surfaces should be
inserted.  It does not duplicate nodes by itself; use the resulting
``Crack_Paths`` set as the controlled insertion target in the Abaqus workflow.
"""
from __future__ import print_function

from abaqus import *
from abaqusConstants import *

MODEL_NAME = 'Model-1'
PART_NAME = 'Specimen'
CRACK_SET_NAME = 'Crack_Paths'


def create_crack_paths_set(L=70.0, t_0=0.25, t_90=0.5, rho_sat=8.0):
    model = mdb.models[MODEL_NAME]
    part = model.parts[PART_NAME]

    n_cols = max(1, int(round(rho_sat * L)))
    dx = L / float(n_cols)
    row_thickness = t_90 / 5.0
    coordinates = []

    for col_idx in range(1, n_cols):
        x_pos = col_idx * dx
        for row_idx in range(5):
            y_mid = t_0 + (row_idx + 0.5) * row_thickness
            coordinates.append(((x_pos, y_mid, 0.0),))

    if not coordinates:
        raise RuntimeError('No crack-path coordinates were generated')

    edges = part.edges.findAt(*coordinates)
    if CRACK_SET_NAME in part.sets.keys():
        del part.sets[CRACK_SET_NAME]
    part.Set(edges=edges, name=CRACK_SET_NAME)

    print('=========================================')
    print('SUCCESS: %d vertical crack-path edge segments grouped.' % len(coordinates))
    print("Set '%s' created successfully." % CRACK_SET_NAME)
    print('=========================================')
    return edges


if __name__ == '__main__':
    create_crack_paths_set()
