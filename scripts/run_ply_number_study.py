# -*- coding: utf-8 -*-
"""Driver for the ply-number parametric study (paper Fig. 9 + 11a).

Runs the Abaqus pipeline for [0/90/0], [0/90]s, [0/902]s laminates. The
[0/90]s and [0/902]s results are reused from the validation sims (they
share the same geometry and material assignment).

Usage (inside Abaqus environment):
    abaqus cae noGUI=scripts/run_ply_number_study.py -- --submit

Python 2.7 compatible.
"""
from __future__ import print_function

import os
import sys
import inspect

from abaqus import mdb
from abaqusConstants import OFF

# Same bootstrap as the original code (proven to work both in noGUI mode
# and File > Run Script mode via inspect.getfile fallback)
try:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))

REPO_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, '..'))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import config
from run_pipeline import run_pipeline


# Only pn_090n0 needs to be run — [0/90]s and [0/902]s come from val_* sims
PLY_NUMBER_NEW_JOBS = ['pn_090n0']
PLY_NUMBER_REUSE = ['val_090s', 'val_0902s']


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
    print('PLY NUMBER STUDY — paper Fig. 9 + 11a')
    print('=' * 70)
    print('New jobs:    %s' % ', '.join(PLY_NUMBER_NEW_JOBS))
    print('Reuse jobs:  %s (run validation sims first!)' % ', '.join(PLY_NUMBER_REUSE))
    print('Submit: %s | Save CAE: %s | Seed: %d | Resume-only: %s' % (
        submit, save_cae, seed, resume_only))
    print('Cohesive mode: %s' % config.COHESIVE_INSERTION_MODE)
    print('=' * 70)

    for i, job_name in enumerate(PLY_NUMBER_NEW_JOBS, 1):
        job = config.get_job_by_name(job_name)
        if job is None:
            print('ERROR: job %s not found in config.JOBS' % job_name)
            continue

        print()
        print('[%d/%d] Processing job: %s (%s)' % (
            i, len(PLY_NUMBER_NEW_JOBS), job_name, job['layup']))

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
    print('PLY NUMBER STUDY — PHASE COMPLETE')
    print('=' * 70)
    if not resume_only and config.COHESIVE_INSERTION_MODE == 'manual':
        print()
        print('NEXT STEPS (manual cohesive insertion):')
        print('  1. Open .cae in Abaqus/CAE:')
        for j in PLY_NUMBER_NEW_JOBS:
            print('       abaqus cae database=abaqus_jobs/%s.cae' % j)
        print('  2. Follow MANUAL_COHESIVE_WORKFLOW.md')
        print('  3. Save each .cae file')
        print('  4. Resume and submit:')
        print('       abaqus cae noGUI=scripts/run_ply_number_study.py -- --resume-only --submit')
    else:
        print()
        print('To produce Fig. 9 + 11a, also post-process these reused jobs:')
        for j in PLY_NUMBER_REUSE:
            print('  abaqus python scripts/postprocess_odb.py --odb abaqus_jobs/%s.odb --job-name %s' % (j, j))
        print()
        print('Then run: python3 scripts/plot_figures.py --figures 9,11a')


if __name__ == '__main__':
    main()
