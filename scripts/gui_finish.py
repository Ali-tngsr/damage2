# -*- coding: utf-8 -*-
"""GUI-driven finish script for Abaqus/CAE.

Run this AFTER manual cohesive insertion. It sets up the assembly, BCs,
step, and creates the Job — without submitting (you submit from Job Manager).

Usage:
  1. After building the model (gui_build.py) and inserting cohesive elements
  2. Save the .cae file (Ctrl+S)
  3. File → Run Script... → select this file (gui_finish.py)
  4. A dialog will appear — enter the job name (must match the build)
  5. BCs and Job are created
  6. Switch to Job module → Job Manager → Submit

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
from boundaryConditions import setup_assembly_and_run


def _show_dialog():
    """Show a dialog to enter the job name."""
    from abaqus import getInputs

    job_list = ', '.join(j['name'] for j in config.JOBS)
    fields = ('Job name:',)
    msg = ('Enter the job name (must match what you used in gui_build.py).\n\n'
           'Valid names: ' + job_list)
    values = getInputs(fields, msg, dialogTitle='Finish Model Setup')
    return values


def main():
    print('=' * 60)
    print('GUI FINISH SCRIPT — BCs + Job Creation')
    print('=' * 60)
    print()
    print('This script assumes:')
    print('  - You already ran gui_build.py')
    print('  - You inserted cohesive elements manually')
    print('  - The model is in memory (or you opened the .cae file)')
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

    print('Setting up BCs and Job for: %s (%s)' % (job_name, job['layup']))
    print('  t0 = %.3f mm' % job['t0_mm'])
    print('  t90 = %.3f mm' % job['t90_mm'])
    print('  total thickness = %.3f mm' % job['total_thickness_mm'])
    print()

    total_thickness = job['total_thickness_mm']

    setup_assembly_and_run(
        L=config.GAUGE_LENGTH_MM,
        total_thickness=total_thickness,
        applied_strain=config.MAX_ENGINEERING_STRAIN,
        job_name=job_name,
        skip_if_exists=True,
    )

    print()
    print('=' * 60)
    print('FINISH COMPLETE — Ready to Submit')
    print('=' * 60)
    print()
    print('NEXT STEPS:')
    print()
    print('  1. Save the .cae file (Ctrl+S)')
    print()
    print('  2. Switch to Job module')
    print()
    print('  3. Open Job Manager (Toolbox icon or Job > Manager)')
    print()
    print('  4. Select job: %s' % job_name)
    print()
    print('  5. Click "Submit"')
    print()
    print('  6. Monitor progress in Job Manager')
    print('     (status: Submitted > Running > Completed)')
    print()
    print('  7. After completion, the .odb file will be in:')
    print('     abaqus_jobs/%s.odb' % job_name)
    print()
    print('  8. Post-process with:')
    print('     abaqus python scripts/postprocess_odb.py \\')
    print('         --odb abaqus_jobs/%s.odb --job-name %s' % (job_name, job_name))
    print('=' * 60)


if __name__ == '__main__':
    main()
