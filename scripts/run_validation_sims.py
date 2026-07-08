# -*- coding: utf-8 -*-
"""Driver for the 3 validation simulations (paper Fig. 5 + 6).

Runs the Abaqus pipeline for [0/90]s, [0/902]s, [0/904]s laminates — all with
t90 = 255 µm elementary ply thickness. Produces 3 .cae / .odb files in
abaqus_jobs/.

Usage (inside Abaqus environment):
    abaqus cae noGUI=scripts/run_validation_sims.py -- --submit
    abaqus cae noGUI=scripts/run_validation_sims.py -- --seed=42
    abaqus cae noGUI=scripts/run_validation_sims.py -- --no-submit --save-cae

Python 2.7 compatible.
"""
from __future__ import print_function

import os
import sys

# =============================================================================
# Robust path bootstrap — works in Abaqus Python 2.7 noGUI mode where
# __file__ may not be defined and sys.argv[0] may be a relative path.
# =============================================================================
def _resolve_script_dir():
    """Find the directory containing this script, trying multiple strategies."""
    try:
        if __file__:
            return os.path.dirname(os.path.abspath(__file__))
    except NameError:
        pass
    try:
        if sys.argv and sys.argv[0]:
            argv0 = sys.argv[0]
            if not os.path.isabs(argv0):
                argv0 = os.path.join(os.getcwd(), argv0)
            if os.path.isfile(argv0):
                return os.path.dirname(os.path.abspath(argv0))
    except (IndexError, AttributeError):
        pass
    try:
        main_mod = sys.modules.get('__main__')
        if main_mod and hasattr(main_mod, '__file__') and main_mod.__file__:
            return os.path.dirname(os.path.abspath(main_mod.__file__))
    except (AttributeError, TypeError):
        pass
    cwd = os.getcwd()
    for candidate in (os.path.join(cwd, 'scripts'), cwd):
        if os.path.isfile(os.path.join(candidate, 'config.py')):
            return os.path.abspath(candidate)
    return None


SCRIPT_DIR = _resolve_script_dir()
if not SCRIPT_DIR:
    print('ERROR: Could not locate script directory.')
    print('Please run this script from the damage2/ repo root:')
    print('  cd <path-to-damage2>')
    print('  abaqus cae noGUI=scripts/run_validation_sims.py -- --no-submit')
    sys.exit(1)

REPO_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, '..'))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
if REPO_DIR not in sys.path:
    sys.path.insert(0, REPO_DIR)

from abaqus import mdb
from abaqusConstants import OFF

import config
from run_pipeline import run_pipeline


# Jobs that constitute the validation set (paper §3.1)
VALIDATION_JOB_NAMES = ['val_090s', 'val_0902s', 'val_0904s']


def _parse_args(argv):
    """Parse --submit, --no-submit, --save-cae, --seed=N, --resume-only flags."""
    user_args = list(argv)
    if '--' in user_args:
        user_args = user_args[user_args.index('--') + 1:]

    submit = '--submit' in user_args
    save_cae = '--save-cae' in user_args or not ('--no-save-cae' in user_args)
    seed = config.DEFAULT_SEED
    for arg in user_args:
        if arg.startswith('--seed='):
            seed = int(arg[len('--seed='):])
    # If --resume-only is given, skip the build phase entirely and only do
    # the resume step (for jobs whose .cae has been manually edited).
    resume_only = '--resume-only' in user_args
    return submit, save_cae, seed, resume_only


def main():
    submit, save_cae, seed, resume_only = _parse_args(sys.argv)

    print('=' * 70)
    print('VALIDATION SIMS — paper Fig. 5 + 6')
    print('=' * 70)
    print('Jobs: %s' % ', '.join(VALIDATION_JOB_NAMES))
    print('Submit: %s | Save CAE: %s | Seed: %d | Resume-only: %s' % (
        submit, save_cae, seed, resume_only))
    print('Cohesive mode: %s' % config.COHESIVE_INSERTION_MODE)
    print('=' * 70)

    for i, job_name in enumerate(VALIDATION_JOB_NAMES, 1):
        job = config.get_job_by_name(job_name)
        if job is None:
            print('ERROR: job %s not found in config.JOBS' % job_name)
            continue

        print()
        print('[%d/%d] Processing job: %s (%s)' % (
            i, len(VALIDATION_JOB_NAMES), job_name, job['layup']))

        # In resume-only mode, skip build and go straight to resume
        if resume_only:
            cae_path = os.path.join(REPO_DIR, 'abaqus_jobs', job_name + '.cae')
            if not os.path.exists(cae_path):
                print('  WARNING: %s not found — skipping (run without --resume-only first)' % cae_path)
                continue
            print('  Resuming from: %s' % cae_path)
            run_pipeline(
                t_0=job['t0_mm'],
                t_90=job['t90_mm'],
                rho_sat=job['rho_sat'],
                seed=seed,
                applied_strain=config.MAX_ENGINEERING_STRAIN,
                save_cae=save_cae,
                submit_job=submit,
                job_name=job_name,
                resume_from=cae_path,
            )
        else:
            # Build mode — pipeline will stop after .cae save (manual mode)
            # or proceed to submission (auto mode)
            run_pipeline(
                L=config.GAUGE_LENGTH_MM,
                t_0=job['t0_mm'],
                t_90=job['t90_mm'],
                rho_sat=job['rho_sat'],
                seed=seed,
                element_size=config.DEFAULT_ELEMENT_SIZE,
                applied_strain=config.MAX_ENGINEERING_STRAIN,
                make_orphan=True,
                save_cae=save_cae,
                submit_job=submit,
                job_name=job_name,
            )

    print()
    print('=' * 70)
    print('VALIDATION SIMS — PHASE COMPLETE')
    print('=' * 70)
    if not resume_only and config.COHESIVE_INSERTION_MODE == 'manual':
        print()
        print('NEXT STEPS (manual cohesive insertion):')
        print('  1. For each job, open .cae in Abaqus/CAE:')
        for j in VALIDATION_JOB_NAMES:
            print('       abaqus cae database=abaqus_jobs/%s.cae' % j)
        print('  2. Follow MANUAL_COHESIVE_WORKFLOW.md to insert cohesive elements')
        print('  3. Save each .cae file')
        print('  4. Resume and submit all jobs:')
        print('       abaqus cae noGUI=scripts/run_validation_sims.py -- --resume-only --submit')
    else:
        print('Output directory: %s/abaqus_jobs/' % REPO_DIR)
        print('Next steps:')
        print('  1. Run post-processing:')
        for j in VALIDATION_JOB_NAMES:
            print('     abaqus python scripts/postprocess_odb.py --odb abaqus_jobs/%s.odb --job-name %s' % (j, j))
        print('  2. Open .odb in Abaqus/CAE for Fig. 6 screenshots')


if __name__ == '__main__':
    main()
