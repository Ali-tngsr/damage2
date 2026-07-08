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


def _find_scripts_dir():
    """Find the damage2/scripts/ directory using multiple strategies."""
    # Strategy 1: __file__ attribute
    try:
        if __file__:
            candidate = os.path.dirname(os.path.abspath(__file__))
            if os.path.isfile(os.path.join(candidate, 'config.py')):
                return candidate
    except NameError:
        pass

    # Strategy 2: inspect current frame
    try:
        frame = inspect.currentframe()
        if frame:
            code = frame.f_code
            if code and code.co_filename:
                candidate = os.path.dirname(os.path.abspath(code.co_filename))
                if os.path.isfile(os.path.join(candidate, 'config.py')):
                    return candidate
    except Exception:
        pass

    # Strategy 3: walk up the call stack
    try:
        frame = inspect.currentframe()
        while frame:
            code = frame.f_code
            if code and code.co_filename and 'gui_finish' in code.co_filename:
                candidate = os.path.dirname(os.path.abspath(code.co_filename))
                if os.path.isfile(os.path.join(candidate, 'config.py')):
                    return candidate
            frame = frame.f_back
    except Exception:
        pass

    # Strategy 4: sys.argv[0]
    try:
        if sys.argv and sys.argv[0]:
            argv0 = sys.argv[0]
            if not os.path.isabs(argv0):
                argv0 = os.path.join(os.getcwd(), argv0)
            if os.path.isfile(argv0):
                candidate = os.path.dirname(os.path.abspath(argv0))
                if os.path.isfile(os.path.join(candidate, 'config.py')):
                    return candidate
    except (IndexError, AttributeError):
        pass

    # Strategy 5: scan cwd
    cwd = os.getcwd()
    candidates = [
        cwd,
        os.path.join(cwd, 'scripts'),
        os.path.dirname(cwd),
        os.path.join(os.path.dirname(cwd), 'scripts'),
    ]
    for candidate in candidates:
        if os.path.isfile(os.path.join(candidate, 'config.py')):
            return os.path.abspath(candidate)

    return None


def _ask_user_for_path():
    """If auto-detection fails, ask the user via dialog."""
    try:
        from abaqus import getInputs
        fields = ('Path to damage2/scripts/ folder:',)
        msg = ('Could not auto-detect the damage2/scripts/ directory.\n\n'
               'Please enter the full path to the scripts/ folder.\n'
               'Example: C:/Users/AVA/Downloads/damage2-dev/scripts')
        values = getInputs(fields, msg, title='Locate scripts folder')
        if values and values[0]:
            path = values[0].strip().strip('"').strip("'")
            if os.path.isfile(os.path.join(path, 'config.py')):
                return path
            if os.path.isfile(os.path.join(path, 'scripts', 'config.py')):
                return os.path.join(path, 'scripts')
    except Exception as e:
        print('Could not show dialog: %s' % e)
    return None


# =============================================================================
# Bootstrap path
# =============================================================================
SCRIPT_DIR = _find_scripts_dir()

if not SCRIPT_DIR:
    print('Auto-detection failed. Asking user for path...')
    SCRIPT_DIR = _ask_user_for_path()

if not SCRIPT_DIR:
    print('ERROR: Could not locate the scripts/ directory.')
    print('Please make sure gui_finish.py is inside the damage2/scripts/ folder,')
    print('or enter the path manually in the dialog.')
    sys.exit(1)

REPO_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, '..'))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
if REPO_DIR not in sys.path:
    sys.path.insert(0, REPO_DIR)

print('Script directory: %s' % SCRIPT_DIR)
print('Repo directory:   %s' % REPO_DIR)

import config
from boundaryConditions import setup_assembly_and_run


def _show_dialog():
    """Show a dialog to enter the job name."""
    from abaqus import getInputs

    job_list = ', '.join(j['name'] for j in config.JOBS)
    fields = ('Job name:',)
    msg = ('Enter the job name (must match what you used in gui_build.py).\n\n'
           'Valid names: ' + job_list)
    values = getInputs(fields, msg, title='Finish Model Setup')
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
