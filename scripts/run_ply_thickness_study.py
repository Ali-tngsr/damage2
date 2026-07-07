# -*- coding: utf-8 -*-
"""Driver for the ply-thickness parametric study (paper Fig. 10 + 11b).

Runs the Abaqus pipeline for [0/90/0] laminates with t90 = 20, 60, 100, 140 µm.

Usage (inside Abaqus environment):
    abaqus cae noGUI=scripts/run_ply_thickness_study.py -- --submit

Python 2.7 compatible.
"""
from __future__ import print_function

import os
import sys

from abaqus import mdb
from abaqusConstants import OFF

try:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
REPO_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, '..'))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import config
from run_pipeline import run_pipeline


# All 4 thickness-study jobs need to be run
THICKNESS_JOBS = ['pt_t90_020', 'pt_t90_060', 'pt_t90_100', 'pt_t90_140']


def _parse_args(argv):
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
    print('PLY THICKNESS STUDY — paper Fig. 10 + 11b')
    print('=' * 70)
    print('Jobs: %s' % ', '.join(THICKNESS_JOBS))
    print('Submit: %s | Save CAE: %s | Seed: %d' % (submit, save_cae, seed))
    print('=' * 70)

    for i, job_name in enumerate(THICKNESS_JOBS, 1):
        job = config.get_job_by_name(job_name)
        if job is None:
            print('ERROR: job %s not found in config.JOBS' % job_name)
            continue

        print()
        print('[%d/%d] Building job: %s (t90 = %.3f mm = %d µm)' % (
            i, len(THICKNESS_JOBS), job_name, job['t90_mm'],
            int(round(job['t90_mm'] * 1000))))

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
    print('PLY THICKNESS STUDY COMPLETE')
    print('=' * 70)
    print()
    print('Next steps:')
    print('  1. Post-process each ODB:')
    for j in THICKNESS_JOBS:
        print('     abaqus python scripts/postprocess_odb.py --odb abaqus_jobs/%s.odb' % j)
    print('  2. Plot: python3 scripts/plot_figures.py --figures 10,11b')


if __name__ == '__main__':
    main()
