# -*- coding: utf-8 -*-
"""Assembly, load step, boundary conditions, and job creation."""
from __future__ import print_function

from abaqus import *
from abaqusConstants import *

# وارد کردن صریح ماژول‌های آباکوس برای اجرای بدون رابط گرافیکی
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
                           job_name=JOB_NAME):
    model = mdb.models[MODEL_NAME]
    assembly = model.rootAssembly
    assembly.DatumCsysByDefault(CARTESIAN)

    part_name = 'Specimen_Orphan' if 'Specimen_Orphan' in model.parts.keys() else 'Specimen'
    part = model.parts[part_name]

# === اعمال جهت‌گیری متریال مستقیماً روی المان‌های شبکه مستقل ===
    import regionToolset
    # === اعمال جهت‌گیری سراسری متریال روی کل شبکه مستقل ===
    import regionToolset
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
    # =======================================================
    # ===============================================================
    if INSTANCE_NAME not in assembly.instances.keys():
        instance = assembly.Instance(name=INSTANCE_NAME, part=part, dependent=ON)
    else:
        instance = assembly.instances[INSTANCE_NAME]

    if 'Step-1' not in model.steps.keys():
        model.StaticStep(name='Step-1', previous='Initial', nlgeom=ON,
                         initialInc=0.005, minInc=1.0e-12, maxInc=0.025,
                         maxNumInc=10000)

    if 'F-Output-1' in model.fieldOutputRequests.keys():
        model.fieldOutputRequests['F-Output-1'].setValues(
            variables=('S', 'E', 'U', 'RF', 'SDEG', 'STATUS', 'DMICRT'))

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
