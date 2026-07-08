# -*- coding: utf-8 -*-
"""Define cohesive material/section and mesh the mesoscale continuum part.

NOTE: Viscous stabilization (DamageStabilizationCohesive) is NOT added
automatically because the keyword name differs across Abaqus versions
(viscosity / cohesiveViscosity / cohesive / etc.) and causes crashes.
If you encounter 'Too many attempts' errors during crack initiation,
add stabilization manually in CAE:
    Property module → Cohesive_Mat → Edit → Damage → Stabilization → 1e-4
"""
from __future__ import print_function

from abaqus import *
from abaqusConstants import *
import mesh
import regionToolset

MODEL_NAME = 'Model-1'
PART_NAME = 'Specimen'
COH_MAT_NAME = 'Cohesive_Mat'
COH_SECTION_NAME = 'Cohesive_Sec'


def create_stochastic_cohesive_materials(model, vf_field, n_cols,
                                          fracture_energy=0.2,
                                          penalty_stiffness=1.0e8):
    """Create per-cell cohesive materials with spatially varied strength Y_T.

    Restored from Ali-tngsr/Damage. Each (col, row) cell uses the local Y_T
    of its assigned Vf, so crack initiation strength follows the stochastic
    Vf field as required by the paper.
    """
    import mesoscale_common
    for col_idx in range(n_cols):
        for row_idx in range(5):
            vf = vf_field[row_idx][col_idx]
            props = mesoscale_common.get_properties(vf, units='MPa')
            yt_local = props['YT']
            mat_name = 'Coh_Mat_C%d_R%d' % (col_idx, row_idx)
            if mat_name not in model.materials.keys():
                material = model.Material(name=mat_name)
                material.Elastic(type=TRACTION,
                                 table=((penalty_stiffness, penalty_stiffness, penalty_stiffness),))
                material.MaxsDamageInitiation(table=((yt_local, yt_local, yt_local),))
                material.maxsDamageInitiation.DamageEvolution(
                    type=ENERGY, softening=LINEAR,
                    table=((fracture_energy,),))
    print('Created %d stochastic cohesive materials.' % (n_cols * 5))


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
    print('  (No viscous stabilization — add manually if convergence fails)')
    return material


def create_cohesive_section(model):
    """Create the cohesive section.

    Uses initialThicknessType=ANALYTICAL with a small thickness (0.001 mm)
    instead of GEOMETRY. This prevents the 'thickness calculated from
    geometry is equal to zero' error that occurs with zero-thickness
    cohesive elements created by the Insert cohesive seams tool.
    """
    if COH_SECTION_NAME not in model.sections.keys():
        try:
            # First try: ANALYTICAL with specified thickness (most reliable)
            model.CohesiveSection(name=COH_SECTION_NAME, material=COH_MAT_NAME,
                                  response=TRACTION_SEPARATION,
                                  initialThicknessType=ANALYTICAL,
                                  initialThickness=0.001)
            print('Cohesive section created (ANALYTICAL, t=0.001): %s' % COH_SECTION_NAME)
        except (TypeError, Exception) as e1:
            print('  ANALYTICAL thickness failed: %s' % e1)
            try:
                # Fallback 1: try with thickness keyword
                model.CohesiveSection(name=COH_SECTION_NAME, material=COH_MAT_NAME,
                                      response=TRACTION_SEPARATION,
                                      initialThicknessType=ANALYTICAL,
                                      thickness=0.001)
                print('Cohesive section created (thickness=0.001): %s' % COH_SECTION_NAME)
            except (TypeError, Exception) as e2:
                print('  thickness keyword failed: %s' % e2)
                try:
                    # Fallback 2: GEOMETRY (may cause zero-thickness error)
                    model.CohesiveSection(name=COH_SECTION_NAME, material=COH_MAT_NAME,
                                          response=TRACTION_SEPARATION,
                                          initialThicknessType=GEOMETRY)
                    print('Cohesive section created (GEOMETRY fallback): %s' % COH_SECTION_NAME)
                    print('  WARNING: GEOMETRY type may cause zero-thickness errors.')
                    print('  If job fails, set thickness manually in Property module.')
                except Exception as e3:
                    print('  WARNING: CohesiveSection creation failed: %s' % e3)
                    return


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
