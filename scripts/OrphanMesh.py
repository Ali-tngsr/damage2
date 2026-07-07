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
        print('COHESIVE INSERTION MODE: MANUAL')
        print('-' * 70)
        print('The orphan mesh has been created but NO cohesive elements')
        print('have been inserted yet. You must do this manually:')
        print()
        print('  1. Save the .cae file (already done by run_pipeline.py)')
        print('  2. Open it in Abaqus/CAE')
        print('  3. Follow MANUAL_COHESIVE_WORKFLOW.md step-by-step')
        print('  4. Save the modified .cae file (overwrite)')
        print('  5. Re-run pipeline with --resume-from=<cae path>')
        print()
        print('Sets available for selection in CAE:')
        print('  - Potential_Crack_Edges  (vertical partition edges)')
        print('  - Ply90_Faces            (90° ply elements)')
        print('  - Cohesive_Sec           (cohesive section, pre-defined)')
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
