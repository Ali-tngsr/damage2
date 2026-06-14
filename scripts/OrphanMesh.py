# -*- coding: utf-8 -*-
"""Create an orphan-mesh copy of the meshed Specimen part."""
from __future__ import print_function

from abaqus import *
from abaqusConstants import *

MODEL_NAME = 'Model-1'
SOURCE_PART = 'Specimen'
ORPHAN_PART = 'Specimen_Orphan'


def make_orphan_mesh():
    model = mdb.models[MODEL_NAME]
    if SOURCE_PART not in model.parts.keys():
        raise RuntimeError("Part '%s' not found. Build and mesh the model first." % SOURCE_PART)

    if ORPHAN_PART in model.parts.keys():
        del model.parts[ORPHAN_PART]

    source = model.parts[SOURCE_PART]
    source.PartFromMesh(name=ORPHAN_PART, copySets=True)

    print('==================================================')
    print("SUCCESS: Orphan Mesh '%s' created with copied sets." % ORPHAN_PART)
    print('==================================================')


if __name__ == '__main__':
    make_orphan_mesh()
