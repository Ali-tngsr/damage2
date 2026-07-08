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


def _add_viscous_stabilization(damage_init, viscosity=1e-4):
    """Add viscous regularization to cohesive damage.

    Tries multiple keyword names across Abaqus versions:
      - viscosity (Abaqus 2020+)
      - cohesiveViscosity (older Abaqus)
      - cohesive (some versions)
      - stabilizationCoefficient
      - stabilization

    If all fail, prints a warning and continues without stabilization
    (the simulation will still run, just may have convergence issues
    during crack initiation).
    """
    keywords_to_try = ['viscosity', 'cohesiveViscosity', 'cohesive',
                       'stabilizationCoefficient', 'stabilization']
    for kw in keywords_to_try:
        try:
            kwargs = {kw: viscosity}
            damage_init.DamageStabilizationCohesive(**kwargs)
            print('  Viscous stabilization added (keyword=%s, value=%g)' % (kw, viscosity))
            return True
        except (TypeError, Exception):
            continue

    # Last-resort: positional argument
    try:
        damage_init.DamageStabilizationCohesive(viscosity)
        print('  Viscous stabilization added (positional, value=%g)' % viscosity)
        return True
    except (TypeError, Exception):
        pass

    print('  WARNING: Could not add viscous stabilization. Continuing without it.')
    print('  If job fails with "Too many attempts" during crack initiation,')
    print('  consider adding stabilization manually in CAE Property module.')
    return False


def create_stochastic_cohesive_materials(model, vf_field, n_cols,
                                          fracture_energy=0.2,
                                          penalty_stiffness=1.0e8):
    """Create per-cell cohesive materials with spatially varied strength Y_T.

    Restored from Ali-tngsr/Damage. Each (col, row) cell uses the local Y_T
    of its assigned Vf, so crack initiation strength follows the stochastic
    Vf field as required by the paper.
    """
    import mesoscale_common
    stabilization_added = False
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
                # Viscous regularization (try multiple keywords, only print warning once)
                if not stabilization_added:
                    stabilization_added = _add_viscous_stabilization(
                        material.maxsDamageInitiation)
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
    # Viscous regularization to prevent Abaqus/Standard crashes
    # (Too many attempts) when cracks initiate.
    _add_viscous_stabilization(material.maxsDamageInitiation)
    print('Cohesive material created: %s' % COH_MAT_NAME)
    return material


def create_cohesive_section(model):
    if COH_SECTION_NAME not in model.sections.keys():
        try:
            model.CohesiveSection(name=COH_SECTION_NAME, material=COH_MAT_NAME,
                                  response=TRACTION_SEPARATION,
                                  initialThicknessType=GEOMETRY)
        except (TypeError, Exception):
            try:
                model.CohesiveSection(name=COH_SECTION_NAME, material=COH_MAT_NAME,
                                      response=TRACTION_SEPARATION)
            except Exception as e:
                print('  WARNING: CohesiveSection creation failed: %s' % e)
                return
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
