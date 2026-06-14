# -*- coding: utf-8 -*-
"""Run the Abaqus mesoscale workflow in one Abaqus/CAE Python session.

Typical use:
    abaqus cae noGUI=scripts/run_pipeline.py -- --submit

The separate scripts share Abaqus' in-memory ``mdb`` object, so this driver is
safer than launching each script in a separate shell process.
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

from build_mesoscale_model import build_model
from Cohesive_Mat import mesh_continuum_part
from Cohesive_Mat2 import create_crack_paths_set
from OrphanMesh import make_orphan_mesh
from boundaryConditions import setup_assembly_and_run

DEFAULT_JOB_NAME = 'Tensile_Test_Stochastic'


def _parse_bool_flag(args, flag_name):
    return flag_name in args


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
                 job_name=DEFAULT_JOB_NAME):
    """Build, mesh, create sets, apply BCs, optionally save and submit the job."""
    total_thickness = (2.0 * t_0) + t_90

    print('--- Step 1/5: building mesoscale model ---')
    build_model(L=L, t_0=t_0, t_90=t_90, rho_sat=rho_sat, seed=seed)

    print('--- Step 2/5: creating cohesive material/section and meshing ---')
    mesh_continuum_part(element_size=element_size)

    print('--- Step 3/5: creating crack-path set ---')
    create_crack_paths_set(L=L, t_0=t_0, t_90=t_90, rho_sat=rho_sat)

    if make_orphan:
        print('--- Step 4/5: creating orphan mesh copy ---')
        make_orphan_mesh()
    else:
        print('--- Step 4/5: orphan mesh skipped ---')

    print('--- Step 5/5: creating assembly, BCs, and job ---')
    setup_assembly_and_run(L=L, total_thickness=total_thickness,
                           applied_strain=applied_strain, job_name=job_name)

    if save_cae:
        job_dir = os.path.join(REPO_DIR, 'abaqus_jobs')
        if not os.path.exists(job_dir):
            os.makedirs(job_dir)
        cae_path = os.path.join(job_dir, job_name + '.cae')
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
        submit_job=_parse_bool_flag(user_args, '--submit'))
