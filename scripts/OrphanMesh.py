# -*- coding: utf-8 -*-
"""Create an orphan-mesh copy of the meshed Specimen part.

In 'manual' cohesive-insertion mode (default), this script only creates the
orphan mesh and reports ready-for-manual-insertion status. The user then
opens the .cae in Abaqus/CAE and inserts cohesive elements via the GUI.

In 'auto' mode (not yet implemented), this script would additionally create
COH2D4 cohesive elements between coincident nodes along the
'Potential_Crack_Edges' set.

Python 2.7 compatible.
"""
from __future__ import print_function

from abaqus import *
from abaqusConstants import *

MODEL_NAME = 'Model-1'
SOURCE_PART = 'Specimen'
ORPHAN_PART = 'Specimen_Orphan'


def make_orphan_mesh(skip_if_manual=True, mode=None):
    """Create an orphan-mesh copy of the meshed Specimen part.

    Parameters
    ----------
    skip_if_manual : bool
        If True and mode is 'manual', only create the orphan mesh and return.
        Cohesive elements will be inserted manually in Abaqus/CAE.
    mode : str, optional
        Override the mode from config.COHESIVE_INSERTION_MODE.
        Values: 'manual' (default) or 'auto' (not yet implemented).
    """
    # Resolve mode
    if mode is None:
        try:
            import config
            mode = config.COHESIVE_INSERTION_MODE
        except ImportError:
            mode = 'manual'

    model = mdb.models[MODEL_NAME]
    if SOURCE_PART not in model.parts.keys():
        raise RuntimeError("Part '%s' not found. Build and mesh the model first." % SOURCE_PART)

    if ORPHAN_PART in model.parts.keys():
        del model.parts[ORPHAN_PART]

    source = model.parts[SOURCE_PART]
    source.PartFromMesh(name=ORPHAN_PART, copySets=True)

    n_nodes = len(source.nodes)
    n_elements = len(source.elements)

    print('=' * 70)
    print("SUCCESS: Orphan Mesh '%s' created with copied sets." % ORPHAN_PART)
    print('  Source part: %s (%d nodes, %d elements)' % (SOURCE_PART, n_nodes, n_elements))
    print('=' * 70)

    if mode == 'manual':
        print()
        print('READY FOR MANUAL COHESIVE INSERTION')
        print('-' * 70)
        print('The orphan mesh is ready. Sets available for selection:')
        print('  - Potential_Crack_Edges  (vertical partition edges in 90° ply)')
        print('  - Crack_Paths            (alternative name)')
        print('  - Ply90_Faces            (90° ply elements)')
        print()
        print('Cohesive material/section already defined:')
        print('  - Cohesive_Mat  (TRACTION + MaxsDamageInitiation + DamageEvolution)')
        print('  - Cohesive_Sec  (response=TRACTION_SEPARATION)')
        print('-' * 70)
    elif mode == 'auto':
        print()
        print('COHESIVE INSERTION MODE: AUTO (not yet implemented)')
        print('Falling back to manual mode. See MANUAL_COHESIVE_WORKFLOW.md.')
    else:
        print('WARNING: unknown cohesive mode %r' % mode)

    return model.parts[ORPHAN_PART]


if __name__ == '__main__':
    make_orphan_mesh()
