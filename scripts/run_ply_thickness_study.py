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
    resume_only = '--resume-only' in user_args
    return submit, save_cae, seed, resume_only


def main():
    submit, save_cae, seed, resume_only = _parse_args(sys.argv)

    print('=' * 70)
    print('PLY THICKNESS STUDY — paper Fig. 10 + 11b')
    print('=' * 70)
    print('Jobs: %s' % ', '.join(THICKNESS_JOBS))
    print('Submit: %s | Save CAE: %s | Seed: %d | Resume-only: %s' % (
        submit, save_cae, seed, resume_only))
    print('Cohesive mode: %s' % config.COHESIVE_INSERTION_MODE)
    print('=' * 70)

    for i, job_name in enumerate(THICKNESS_JOBS, 1):
        job = config.get_job_by_name(job_name)
        if job is None:
            print('ERROR: job %s not found in config.JOBS' % job_name)
            continue

        print()
        print('[%d/%d] Processing job: %s (t90 = %.3f mm = %d µm)' % (
            i, len(THICKNESS_JOBS), job_name, job['t90_mm'],
            int(round(job['t90_mm'] * 1000))))

        if resume_only:
            cae_path = os.path.join(REPO_DIR, 'abaqus_jobs', job_name + '.cae')
            if not os.path.exists(cae_path):
                print('  WARNING: %s not found — skipping' % cae_path)
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
    print('PLY THICKNESS STUDY — PHASE COMPLETE')
    print('=' * 70)
    if not resume_only and config.COHESIVE_INSERTION_MODE == 'manual':
        print()
        print('NEXT STEPS (manual cohesive insertion):')
        print('  1. Open .cae in Abaqus/CAE:')
        for j in THICKNESS_JOBS:
            print('       abaqus cae database=abaqus_jobs/%s.cae' % j)
        print('  2. Follow MANUAL_COHESIVE_WORKFLOW.md')
        print('  3. Save each .cae file')
        print('  4. Resume and submit:')
        print('       abaqus cae noGUI=scripts/run_ply_thickness_study.py -- --resume-only --submit')
    else:
        print()
        print('Next steps:')
        print('  1. Post-process each ODB:')
        for j in THICKNESS_JOBS:
            print('     abaqus python scripts/postprocess_odb.py --odb abaqus_jobs/%s.odb --job-name %s' % (j, j))
        print('  2. Plot: python3 scripts/plot_figures.py --figures 10,11b')


if __name__ == '__main__':
    main()
