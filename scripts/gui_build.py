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


def _find_scripts_dir():
    """Find the damage2/scripts/ directory using multiple strategies.

    When running via File > Run Script, Abaqus uses execfile() which does
    NOT set __file__. We try several fallback strategies.
    """
    # Strategy 1: __file__ attribute (normal Python, abaqus cae noGUI)
    try:
        if __file__:
            candidate = os.path.dirname(os.path.abspath(__file__))
            if os.path.isfile(os.path.join(candidate, 'config.py')):
                return candidate
    except NameError:
        pass

    # Strategy 2: inspect current frame (works in execfile mode sometimes)
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

    # Strategy 3: walk up the call stack looking for this script
    try:
        frame = inspect.currentframe()
        while frame:
            code = frame.f_code
            if code and code.co_filename and 'gui_build' in code.co_filename:
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

    # Strategy 5: scan cwd and common locations
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
            # Maybe they gave the repo root
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
    print('Please make sure gui_build.py is inside the damage2/scripts/ folder,')
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
from run_pipeline import run_pipeline


def _show_dialog():
    """Show a dialog to select which job to build."""
    from abaqus import getInputs

    job_list = '\n'.join(['  %d. %s (%s, t90=%.3f mm)' % (
        i + 1, j['name'], j['layup'], j['t90_mm'])
        for i, j in enumerate(config.JOBS)])

    fields = ('Job name (e.g. val_090s):',)
    msg = 'Available jobs:\n' + job_list + '\n\nEnter the job name to build:'
    values = getInputs(fields, msg, title='Build Model')
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
