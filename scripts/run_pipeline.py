# -*- coding: utf-8 -*-
"""Run the Abaqus mesoscale workflow in one Abaqus/CAE Python session.

Two operating modes:

  Manual mode (default, RECOMMENDED for paper replication):
      abaqus cae noGUI=scripts/run_pipeline.py -- --t90=0.255 --job-name=val_090s
      → Builds geometry, mesh, edge sets, saves .cae, then EXITS.
      → User opens .cae in Abaqus/CAE, inserts cohesive elements manually
        (see MANUAL_COHESIVE_WORKFLOW.md), saves the .cae.
      → Re-run with --resume-from to submit:
        abaqus cae noGUI=scripts/run_pipeline.py -- \\
            --resume-from=abaqus_jobs/val_090s.cae --submit --job-name=val_090s

  Resume mode (after manual cohesive insertion):
      abaqus cae noGUI=scripts/run_pipeline.py -- \\
          --resume-from=abaqus_jobs/val_090s.cae --submit

The separate scripts share Abaqus' in-memory ``mdb`` object, so this driver is
safer than launching each script in a separate shell process.

Python 2.7 compatible.
"""
from __future__ import print_function

import os
import sys

from abaqus import mdb
from abaqusConstants import OFF

import inspect
try:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))

REPO_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, '..'))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import config
from build_mesoscale_model import build_model
from Cohesive_Mat import mesh_continuum_part
from Cohesive_Mat2 import create_crack_paths_set
from OrphanMesh import make_orphan_mesh
from boundaryConditions import setup_assembly_and_run

DEFAULT_JOB_NAME = 'Tensile_Test_Stochastic'


def _parse_bool_flag(args, flag_name):
    return flag_name in args


def _parse_str(args, name, default_value=None):
    prefix = '--%s=' % name
    for arg in args:
        if arg.startswith(prefix):
            return arg[len(prefix):]
    return default_value


def _parse_float(args, name, default_value):
    prefix = '--%s=' % name
    for arg in args:
        if arg.startswith(prefix):
            return float(arg[len(prefix):])
    return default_value


def _parse_int(args, name, default_value):
    prefix = '--%s=' % name
    for arg in args:
        if arg.startswith(prefix):
            return int(arg[len(prefix):])
    return default_value


def _abaqus_user_args(argv):
    """Return arguments after Abaqus' conventional '--' separator."""
    if '--' in argv:
        return argv[argv.index('--') + 1:]
    return argv[1:]


def run_pipeline(L=70.0, t_0=0.25, t_90=0.5, rho_sat=8.0, seed=42,
                 element_size=0.125, applied_strain=0.025,
                 make_orphan=True, save_cae=True, submit_job=False,
                 job_name=DEFAULT_JOB_NAME, resume_from=None,
                 cohesive_mode=None):
    """Build, mesh, create sets, apply BCs, optionally save and submit the job.

    Parameters
    ----------
    resume_from : str or None
        If given, open this .cae file (which user has manually edited to
        insert cohesive elements) and skip the build/mesh/orphan steps.
        Goes directly to assembly/BC/job creation and optional submission.
    cohesive_mode : str or None
        Override config.COHESIVE_INSERTION_MODE for this run.
        Values: 'manual' (default) or 'auto' (not implemented).
    """
    # Resolve cohesive mode
    if cohesive_mode is None:
        cohesive_mode = config.COHESIVE_INSERTION_MODE

    # =====================================================================
    # RESUME MODE: load existing .cae and skip build steps
    # =====================================================================
    if resume_from is not None:
        if not os.path.isabs(resume_from):
            resume_from = os.path.join(REPO_DIR, resume_from)
        if not os.path.exists(resume_from):
            raise RuntimeError('Resume file not found: %s' % resume_from)

        print('=' * 70)
        print('RESUME MODE — loading user-edited .cae')
        print('=' * 70)
        print('  File: %s' % resume_from)
        print('  (Cohesive elements should already be inserted by user.)')
        print('=' * 70)

        mdb.open(resume_from)

        total_thickness = (2.0 * t_0) + t_90
        print('--- Setting up assembly, BCs, and job (skip_if_exists=True) ---')
        setup_assembly_and_run(L=L, total_thickness=total_thickness,
                               applied_strain=applied_strain,
                               job_name=job_name, skip_if_exists=True)

        if save_cae:
            job_dir = os.path.join(REPO_DIR, 'abaqus_jobs')
            if not os.path.exists(job_dir):
                os.makedirs(job_dir)
            cae_path = os.path.join(job_dir, job_name + '.cae')
            mdb.saveAs(pathName=cae_path)
            print('Saved (post-resume) CAE model to: %s' % cae_path)

        if submit_job:
            print('Submitting job: %s' % job_name)
            mdb.jobs[job_name].submit(consistencyChecking=OFF)
            mdb.jobs[job_name].waitForCompletion()
            print('Job completed: %s' % job_name)
        else:
            print('Job was created but not submitted. Re-run with --submit.')
        return

    # =====================================================================
    # BUILD MODE: construct model from scratch
    # =====================================================================
    total_thickness = (2.0 * t_0) + t_90

    print('--- Step 1/5: building mesoscale model ---')
    build_model(L=L, t_0=t_0, t_90=t_90, rho_sat=rho_sat, seed=seed)

    print('--- Step 2/5: creating cohesive material/section and meshing ---')
    mesh_continuum_part(element_size=element_size)

    print('--- Step 3/5: creating crack-path set ---')
    create_crack_paths_set(L=L, t_0=t_0, t_90=t_90, rho_sat=rho_sat)

    if make_orphan:
        print('--- Step 4/5: creating orphan mesh copy ---')
        make_orphan_mesh(mode=cohesive_mode)
    else:
        print('--- Step 4/5: orphan mesh skipped ---')

    # Save .cae BEFORE assembly/BC setup so user can pick it up for
    # manual cohesive insertion.
    job_dir = os.path.join(REPO_DIR, 'abaqus_jobs')
    if not os.path.exists(job_dir):
        os.makedirs(job_dir)
    cae_path = os.path.join(job_dir, job_name + '.cae')

    if save_cae:
        mdb.saveAs(pathName=cae_path)
        print('Saved CAE model (pre-assembly) to: %s' % cae_path)

    # =====================================================================
    # MANUAL MODE: stop here, ask user to insert cohesive elements
    # =====================================================================
    if cohesive_mode == 'manual':
        print()
        print('=' * 70)
        print('READY FOR MANUAL COHESIVE INSERTION')
        print('=' * 70)
        print()
        print('The .cae file has been saved with:')
        print('  - Geometry (0° and 90° plies partitioned)')
        print('  - Mesh of CPS4R continuum elements')
        print('  - Edge set: Potential_Crack_Edges (and Crack_Paths)')
        print('  - Cohesive material: Cohesive_Mat')
        print('  - Cohesive section: Cohesive_Sec')
        print()
        print('NEXT STEPS:')
        print()
        print('  1. Open the .cae in Abaqus/CAE:')
        print('       abaqus cae database=%s' % cae_path)
        print()
        print('  2. In Mesh module, use Mesh > Edit > Element > Create')
        print('     to insert COH2D4 elements along the edges in the')
        print('     Potential_Crack_Edges set.')
        print('     See MANUAL_COHESIVE_WORKFLOW.md for step-by-step guide.')
        print()
        print('  3. Save the .cae file (Ctrl+S).')
        print()
        print('  4. Resume the pipeline to apply BCs and submit:')
        print('       abaqus cae noGUI=scripts/run_pipeline.py -- \\')
        print('           --resume-from=%s' % cae_path)
        print('           --submit --job-name=%s' % job_name)
        print('           --t0=%.3f --t90=%.3f' % (t_0, t_90))
        print()
        print('  Or submit all jobs in a batch (see MANUAL_COHESIVE_WORKFLOW.md §8).')
        print()
        print('=' * 70)
        return

    # =====================================================================
    # AUTO MODE (not yet implemented): would proceed to assembly/BC/submit
    # =====================================================================
    print('--- Step 5/5: creating assembly, BCs, and job ---')
    setup_assembly_and_run(L=L, total_thickness=total_thickness,
                           applied_strain=applied_strain, job_name=job_name)

    if save_cae:
        mdb.saveAs(pathName=cae_path)
        print('Saved CAE model to: %s' % cae_path)

    if submit_job:
        print('Submitting job: %s' % job_name)
        mdb.jobs[job_name].submit(consistencyChecking=OFF)
        mdb.jobs[job_name].waitForCompletion()
        print('Job completed: %s' % job_name)
    else:
        print('Job was created but not submitted. Submit it from Abaqus/CAE or rerun with --submit.')


if __name__ == '__main__':
    user_args = _abaqus_user_args(sys.argv)
    run_pipeline(
        L=_parse_float(user_args, 'L', 70.0),
        t_0=_parse_float(user_args, 't0', 0.25),
        t_90=_parse_float(user_args, 't90', 0.5),
        rho_sat=_parse_float(user_args, 'rho-sat', 8.0),
        seed=_parse_int(user_args, 'seed', 42),
        element_size=_parse_float(user_args, 'element-size', 0.125),
        applied_strain=_parse_float(user_args, 'strain', 0.025),
        make_orphan=not _parse_bool_flag(user_args, '--no-orphan'),
        save_cae=not _parse_bool_flag(user_args, '--no-save'),
        submit_job=_parse_bool_flag(user_args, '--submit'),
        job_name=_parse_str(user_args, 'job-name', DEFAULT_JOB_NAME),
        resume_from=_parse_str(user_args, 'resume-from', None),
        cohesive_mode=_parse_str(user_args, 'cohesive-mode', None),
    )
