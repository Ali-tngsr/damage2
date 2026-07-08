# -*- coding: utf-8 -*-
"""GUI-driven build script for Abaqus/CAE.

Usage:
  1. Open Abaqus/CAE (just type: abaqus cae)
  2. File → Run Script... → select this file (gui_build.py)
  3. A dialog will appear — enter the job name (e.g. val_090s)
  4. The script builds geometry, mesh, materials, edge sets, and saves .cae
  5. The model stays in memory — proceed with manual cohesive insertion
  6. After saving, run gui_finish.py to set up BCs and Job

Python 2.7 compatible (runs inside Abaqus/CAE).
"""
from __future__ import print_function

import os
import sys
import inspect

# Same bootstrap as the original run_pipeline.py (proven to work both in
# noGUI mode and File > Run Script mode via inspect.getfile fallback)
try:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))

REPO_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, '..'))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import config
from run_pipeline import run_pipeline


def _show_dialog():
    """Show a dialog to select which job to build."""
    from abaqus import getInputs

    job_list = '\n'.join(['  %d. %s (%s, t90=%.3f mm)' % (
        i + 1, j['name'], j['layup'], j['t90_mm'])
        for i, j in enumerate(config.JOBS)])

    fields = ('Job name (e.g. val_090s):',)
    msg = 'Available jobs:\n' + job_list + '\n\nEnter the job name to build:'
    values = getInputs(fields, msg, dialogTitle='Build Model')
    return values


def main():
    print('=' * 60)
    print('GUI BUILD SCRIPT')
    print('=' * 60)
    print()
    print('Available jobs:')
    for i, j in enumerate(config.JOBS):
        print('  %d. %s (%s, t90=%.3f mm)' % (
            i + 1, j['name'], j['layup'], j['t90_mm']))
    print()

    # Show dialog
    values = _show_dialog()
    if not values or not values[0]:
        print('Cancelled by user.')
        return

    job_name = values[0].strip()
    job = config.get_job_by_name(job_name)
    if job is None:
        print('ERROR: job "%s" not found in config.JOBS' % job_name)
        print('Valid job names: %s' % ', '.join(j['name'] for j in config.JOBS))
        return

    print('Building job: %s (%s)' % (job_name, job['layup']))
    print('  t0 = %.3f mm' % job['t0_mm'])
    print('  t90 = %.3f mm' % job['t90_mm'])
    print('  total thickness = %.3f mm' % job['total_thickness_mm'])
    print()

    # Run the pipeline in build mode (no submit)
    run_pipeline(
        L=config.GAUGE_LENGTH_MM,
        t_0=job['t0_mm'],
        t_90=job['t90_mm'],
        rho_sat=job['rho_sat'],
        seed=config.DEFAULT_SEED,
        element_size=config.DEFAULT_ELEMENT_SIZE,
        applied_strain=config.MAX_ENGINEERING_STRAIN,
        make_orphan=True,
        save_cae=True,
        submit_job=False,
        job_name=job_name,
    )

    print()
    print('=' * 60)
    print('BUILD COMPLETE — Model is in memory')
    print('=' * 60)
    print()
    print('NEXT STEPS:')
    print()
    print('  1. Switch to Mesh module')
    print('  2. Use Mesh > Edit > Element > Create to insert COH2D4')
    print('     elements along the Potential_Crack_Edges set')
    print('     (See MANUAL_COHESIVE_WORKFLOW.md for details)')
    print()
    print('  3. Save the .cae file (Ctrl+S)')
    print()
    print('  4. File > Run Script... > gui_finish.py')
    print('     to set up BCs and create the Job')
    print()
    print('  5. In Job module: Job Manager > Submit')
    print('=' * 60)


if __name__ == '__main__':
    main()
