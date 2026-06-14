# -*- coding: utf-8 -*-
"""Define cohesive material/section and mesh the mesoscale continuum part."""
from __future__ import print_function

from abaqus import *
from abaqusConstants import *
import mesh
import regionToolset

MODEL_NAME = 'Model-1'
PART_NAME = 'Specimen'
COH_MAT_NAME = 'Cohesive_Mat'
COH_SECTION_NAME = 'Cohesive_Sec'


def create_cohesive_material(model, strength=17.0, fracture_energy=0.2,
                             penalty_stiffness=1.0e8):
    """Create the baseline bilinear traction-separation cohesive material."""
    if COH_MAT_NAME in model.materials.keys():
        return model.materials[COH_MAT_NAME]

    material = model.Material(name=COH_MAT_NAME)
    material.Elastic(type=TRACTION,
                     table=((penalty_stiffness, penalty_stiffness, penalty_stiffness),))
    material.MaxsDamageInitiation(table=((strength, strength, strength),))
    material.maxsDamageInitiation.DamageEvolution(type=ENERGY, softening=LINEAR,
                                                  table=((fracture_energy,),))
    print('Cohesive material created: %s' % COH_MAT_NAME)
    return material


def create_cohesive_section(model):
    if COH_SECTION_NAME not in model.sections.keys():
        model.CohesiveSection(name=COH_SECTION_NAME, material=COH_MAT_NAME,
                              response=TRACTION_SEPARATION,
                              initialThicknessType=GEOMETRY)
        print('Cohesive section created: %s' % COH_SECTION_NAME)


def mesh_continuum_part(element_size=0.125):
    """Assign plane-stress elements and generate the mesh for Specimen."""
    model = mdb.models[MODEL_NAME]
    part = model.parts[PART_NAME]

    create_cohesive_material(model)
    create_cohesive_section(model)

    part.seedPart(size=element_size, deviationFactor=0.1, minSizeFactor=0.1)
    face_region = regionToolset.Region(faces=part.faces)
    element_type = mesh.ElemType(elemCode=CPS4R, elemLibrary=STANDARD)
    part.setElementType(regions=face_region, elemTypes=(element_type,))
    part.generateMesh()
    print('Continuum mesh generated for %s with element size %g.' % (PART_NAME, element_size))


if __name__ == '__main__':
    mesh_continuum_part()
