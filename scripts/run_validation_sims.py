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

from abaqus import mdb
from abaqusConstants import OFF

# Resolve script and repo paths so the script works from any CWD
try:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
REPO_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, '..'))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import config
from run_pipeline import run_pipeline


# Jobs that constitute the validation set (paper §3.1)
VALIDATION_JOB_NAMES = ['val_090s', 'val_0902s', 'val_0904s']


def _parse_args(argv):
    """Parse --submit, --no-submit, --save-cae, --seed=N flags."""
    user_args = list(argv)
    if '--' in user_args:
        user_args = user_args[user_args.index('--') + 1:]

    submit = '--submit' in user_args
    save_cae = '--save-cae' in user_args or not ('--no-save-cae' in user_args)
    seed = config.DEFAULT_SEED
    for arg in user_args:
        if arg.startswith('--seed='):
            seed = int(arg[len('--seed='):])
    return submit, save_cae, seed


def main():
    submit, save_cae, seed = _parse_args(sys.argv)

    print('=' * 70)
    print('VALIDATION SIMS — paper Fig. 5 + 6')
    print('=' * 70)
    print('Jobs: %s' % ', '.join(VALIDATION_JOB_NAMES))
    print('Submit: %s | Save CAE: %s | Seed: %d' % (submit, save_cae, seed))
    print('=' * 70)

    for i, job_name in enumerate(VALIDATION_JOB_NAMES, 1):
        job = config.get_job_by_name(job_name)
        if job is None:
            print('ERROR: job %s not found in config.JOBS' % job_name)
            continue

        print()
        print('[%d/%d] Building job: %s (%s)' % (i, len(VALIDATION_JOB_NAMES),
                                                  job_name, job['layup']))

        # Use the t90 of the validation case. For multi-ply 90° stacks,
        # run_pipeline treats the whole 90° block as one region with the
        # given total thickness.
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
    print('VALIDATION SIMS COMPLETE')
    print('=' * 70)
    print('Output directory: %s/abaqus_jobs/' % REPO_DIR)
    print('Next steps:')
    print('  1. Run post-processing:')
    print('     abaqus python scripts/postprocess_odb.py --odb abaqus_jobs/val_090s.odb')
    print('  2. Open .odb in Abaqus/CAE for Fig. 6 screenshots')
    if not submit:
        print('  (Jobs were created but NOT submitted. Re-run with --submit to run them.)')


if __name__ == '__main__':
    main()
