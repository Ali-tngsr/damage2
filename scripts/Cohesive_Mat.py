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
    """Create the cohesive section with viscous stabilization via Section Controls.

    For cohesive elements with TRACTION_SEPARATION response, viscosity CANNOT
    be defined via *DAMAGE STABILIZATION in the material. Instead, it must be
    defined via *SECTION CONTROLS in the section.

    This prevents the warning:
      'COHESIVE ELEMENTS WITH TRACTION SEPARATION RESPONSE CANNOT USE
       *DAMAGE STABILIZATION. VISCOSITY SHOULD BE DEFINED BY USING
       *SECTION CONTROLS'

    Uses initialThicknessType=ANALYTICAL with thickness=0.001 to prevent
    the zero-thickness error.
    """
    if COH_SECTION_NAME not in model.sections.keys():
        try:
            # Create cohesive section with ANALYTICAL thickness
            model.CohesiveSection(name=COH_SECTION_NAME, material=COH_MAT_NAME,
                                  response=TRACTION_SEPARATION,
                                  initialThicknessType=ANALYTICAL,
                                  initialThickness=0.001)
            print('Cohesive section created (ANALYTICAL, t=0.001): %s' % COH_SECTION_NAME)

            # Add Section Controls for viscous stabilization
            # This is the ONLY way to add viscosity to traction-separation cohesive elements
            section = model.sections[COH_SECTION_NAME]
            try:
                # Try different keyword names for viscosity across Abaqus versions
                viscosity_keywords = ['viscosity', 'stabilizationCoefficient',
                                      'dampingViscosity', 'cohesiveViscosity']
                viscosity_added = False
                for kw in viscosity_keywords:
                    try:
                        kwargs = {'viscosity': 1e-4} if kw == 'viscosity' else {kw: 1e-4}
                        section.SectionControls(**kwargs)
                        print('  Viscous stabilization added via SectionControls (keyword=%s, value=1e-4)' % kw)
                        viscosity_added = True
                        break
                    except (TypeError, Exception):
                        continue

                if not viscosity_added:
                    # Try alternative API: sectionControls() at model level
                    try:
                        model.SectionControls(name='Coh_Sec_Controls', viscosity=1e-4)
                        print('  Viscous stabilization added via model.SectionControls')
                        viscosity_added = True
                    except Exception:
                        pass

                if not viscosity_added:
                    print('  Note: Could not auto-add Section Controls viscosity.')
                    print('  If convergence fails, add manually:')
                    print('    Property > Section > Cohesive_Sec > Edit > Section Controls > Viscosity: 1e-4')
            except Exception as e:
                print('  Note: SectionControls failed: %s' % e)
                print('  Add viscosity manually if needed.')

        except (TypeError, Exception) as e1:
            print('  ANALYTICAL thickness failed: %s' % e1)
            try:
                model.CohesiveSection(name=COH_SECTION_NAME, material=COH_MAT_NAME,
                                      response=TRACTION_SEPARATION,
                                      initialThicknessType=GEOMETRY)
                print('Cohesive section created (GEOMETRY fallback): %s' % COH_SECTION_NAME)
                print('  WARNING: GEOMETRY type may cause zero-thickness errors.')
            except Exception as e2:
                print('  WARNING: CohesiveSection creation failed: %s' % e2)
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
