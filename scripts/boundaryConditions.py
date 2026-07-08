# -*- coding: utf-8 -*-
"""Assembly, load step, boundary conditions, and job creation.

Python 2.7 compatible. Imports explicit Abaqus modules so the script can run
in noGUI mode without the interactive CAE session.
"""
from __future__ import print_function

from abaqus import *
from abaqusConstants import *

import regionToolset
import part
import assembly
import step
import load
import job

MODEL_NAME = 'Model-1'


INSTANCE_NAME = 'Specimen_Inst'
JOB_NAME = 'Tensile_Test_Stochastic'


def _delete_set_if_exists(assembly, set_name):
    if set_name in assembly.sets.keys():
        del assembly.sets[set_name]


def setup_assembly_and_run(L=70.0, total_thickness=1.0, applied_strain=0.025,
                           job_name=JOB_NAME, skip_if_exists=False):
    """Set up assembly, BCs, step, and job.

    Parameters
    ----------
    L : float
        Specimen gauge length (mm).
    total_thickness : float
        Total laminate thickness (mm) — used for BC node selection.
    applied_strain : float
        Max applied engineering strain (default 0.025 = 2.5%).
    job_name : str
        Abaqus job name.
    skip_if_exists : bool
        If True, skip assembly/step/BC creation if they already exist
        (used when resuming from a manually-edited .cae file).
    """
    model = mdb.models[MODEL_NAME]
    assembly = model.rootAssembly

    # If resuming from a manually-edited .cae (cohesive elements already
    # inserted by user), the assembly/BCs may already exist — skip them.
    if skip_if_exists and INSTANCE_NAME in assembly.instances.keys():
        print('Assembly already exists (resume mode) — Intercepting and fixing manual cohesive elements...')

        part_name = 'Specimen_Orphan' if 'Specimen_Orphan' in model.parts.keys() else 'Specimen'
        p = model.parts[part_name]

        # Automatically fix Element Type and Section Assignment for manually inserted seams
        if 'CohesiveSeam-1-Elements' in p.sets.keys():
            import mesh
            coh_set = p.sets['CohesiveSeam-1-Elements']

            # 1. Force Element Type to COH2D4 (Standard Mechanical Library)
            elemType = mesh.ElemType(elemCode=COH2D4, elemLibrary=STANDARD)
            p.setElementType(regions=(coh_set,), elemTypes=(elemType,))

            # 2. Assign Cohesive Section
            p.SectionAssignment(region=coh_set, sectionName='Cohesive_Sec',
                                offset=0.0, offsetType=MIDDLE_SURFACE,
                                offsetField='', thicknessAssignment=FROM_SECTION)
            print('SUCCESS: Forced CohesiveSeam-1-Elements to COH2D4 and assigned Cohesive_Sec automatically.')
        else:
            print('WARNING: CohesiveSeam-1-Elements set not found in part!')

        if job_name not in mdb.jobs.keys():
            mdb.Job(name=job_name, model=MODEL_NAME,
                    description='Mesoscale transverse cracking simulation',
                    numCpus=4, numDomains=4)
        print('Job created: %s' % job_name)
        return

    assembly.DatumCsysByDefault(CARTESIAN)

    # Prefer orphan mesh if it exists (created by OrphanMesh.make_orphan_mesh).
    # In manual mode, the user may have also added cohesive elements directly
    # to the orphan mesh part.
    part_name = 'Specimen_Orphan' if 'Specimen_Orphan' in model.parts.keys() else 'Specimen'
    part = model.parts[part_name]

    # === اعمال جهت‌گیری سراسری متریال روی المان‌های شبکه مستقل ===
    # NOTE: this orientation applies to orphan-mesh elements (not faces).
    # The face-level orientation is set separately in build_mesoscale_model.py.
    all_elements = part.elements
    part.MaterialOrientation(
        region=regionToolset.Region(elements=all_elements),
        orientationType=GLOBAL,
        axis=AXIS_3,
        additionalRotationType=ROTATION_NONE,
        localCsys=None,
        fieldName='',
        stackDirection=STACK_3
    )
    # ===========================================================
    if INSTANCE_NAME not in assembly.instances.keys():
        instance = assembly.Instance(name=INSTANCE_NAME, part=part, dependent=ON)
    else:
        instance = assembly.instances[INSTANCE_NAME]

    if 'Step-1' not in model.steps.keys():
        model.StaticStep(name='Step-1', previous='Initial', nlgeom=ON,
                         initialInc=0.005, minInc=1.0e-12, maxInc=0.025,
                         maxNumInc=10000)

    # ===============================================================
    # تنظیمات خروجی میدانی (Field Output) — خروجی‌های عمومی برای کل قطعه
    # شامل SDEG, STATUS, DMICRT برای ردیابی پیشرفت ترک در المان‌های کوهیزیو
    # ===============================================================
    if 'F-Output-1' in model.fieldOutputRequests.keys():
        model.fieldOutputRequests['F-Output-1'].setValues(
            variables=('S', 'E', 'U', 'RF', 'SDEG', 'STATUS', 'DMICRT'),
            frequency=20)  # save every 20 increments (controls ODB size)

    tol = 1.0e-4
    # تغییر از edges به nodes به دلیل استفاده از Orphan Mesh
    left_nodes = instance.nodes.getByBoundingBox(xMin=-tol, yMin=-tol, zMin=-tol,
                                                xMax=tol, yMax=total_thickness + tol, zMax=tol)
    right_nodes = instance.nodes.getByBoundingBox(xMin=L - tol, yMin=-tol, zMin=-tol,
                                                 xMax=L + tol, yMax=total_thickness + tol, zMax=tol)
    bottom_nodes = instance.nodes.getByBoundingBox(xMin=-tol, yMin=-tol, zMin=-tol,
                                                  xMax=L + tol, yMax=tol, zMax=tol)

    for set_name in ('Left_Edge', 'Right_Edge', 'Bottom_Edge'):
        _delete_set_if_exists(assembly, set_name)
        
    left_set = assembly.Set(nodes=left_nodes, name='Left_Edge')
    right_set = assembly.Set(nodes=right_nodes, name='Right_Edge')
    bottom_set = assembly.Set(nodes=bottom_nodes, name='Bottom_Edge')

    if 'Fix_Left_X' not in model.boundaryConditions.keys():
        model.DisplacementBC(name='Fix_Left_X', createStepName='Step-1',
                             region=left_set, u1=0.0)
    if 'Fix_Bottom_Y' not in model.boundaryConditions.keys():
        model.DisplacementBC(name='Fix_Bottom_Y', createStepName='Step-1',
                             region=bottom_set, u2=0.0)
    if 'Pull_Right_X' not in model.boundaryConditions.keys():
        model.DisplacementBC(name='Pull_Right_X', createStepName='Step-1',
                             region=right_set, u1=applied_strain * L)

    if job_name not in mdb.jobs.keys():
        mdb.Job(name=job_name, model=MODEL_NAME,
                description='Mesoscale transverse cracking simulation',
                numCpus=4, numDomains=4)

    print('==================================================')
    print('SUCCESS: Assembly, step, BCs, and job created.')
    print('Applied displacement: %g mm (%g strain)' % (applied_strain * L, applied_strain))
    print('Job Name: %s' % job_name)
    print('==================================================')


if __name__ == '__main__':
    setup_assembly_and_run()
