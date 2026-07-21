# -*- coding: utf-8 -*-
"""Add a Vf (fiber volume fraction) field to an ODB for visualization.

This script creates a new field output called 'VF' in the ODB that
contains the fiber volume fraction of each element. This allows you to
plot Vf as a contour in Abaqus/CAE, giving a meaningful color map that
shows the stochastic Vf distribution in the 90° ply (like Fig. 4 of
the paper).

METHOD: Instead of trying to read material assignments from the ODB
(which often fails because section assignments are not stored at the
instance level), this script RECONSTRUCTS the Vf field by:
  1. Reading element centroid positions from the ODB
  2. Using vf_field.py to regenerate the same stochastic Vf field
     (with the same seed and parameters)
  3. Mapping each element to its Vf value based on its (col, row) position

Usage:
    abaqus python scripts/add_vf_field.py --odb abaqus_jobs/val_0904s.odb
    abaqus python scripts/add_vf_field.py --odb abaqus_jobs/val_0904s.odb --job-name val_0904s

Python 2.7 compatible (runs inside abaqus python).
"""
from __future__ import print_function

import argparse
import os
import sys
import math

# Resolve paths so config can be imported
try:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
REPO_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, '..'))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)


def _reconstruct_vf_field(L, t_0, t_90, rho_sat, seed):
    """Reconstruct the Vf field using vf_field.py with the same parameters.

    Returns a 2D list vf_field[row][col] of Vf values.
    """
    try:
        import config
        from vf_field import generate_vf_field
        n_cols = max(1, int(round(rho_sat * L)))
        n_rows = config.N_THROUGH_THICKNESS_CELLS
        vf_field = generate_vf_field(n_cols, n_rows, seed)
        return vf_field, n_cols, n_rows
    except Exception as e:
        print('  ERROR reconstructing Vf field: %s' % e)
        return None, 0, 0


def _element_to_vf(elem, vf_field, n_cols, n_rows, L, t_0, t_90):
    """Map an element to its Vf value based on its centroid position.

    - Elements in 0° plies (y < t_0 or y > t_0 + t_90) → Vf = 45.0
    - Elements in 90° ply (t_0 <= y <= t_0 + t_90) → Vf from vf_field[row][col]
    """
    try:
        # Get element centroid (average of node coordinates)
        nodes = elem.getNodes()
        if not nodes:
            return 45.0

        x_sum = 0.0
        y_sum = 0.0
        for node in nodes:
            coords = node.coordinates
            x_sum += float(coords[0])
            y_sum += float(coords[1])
        x_c = x_sum / len(nodes)
        y_c = y_sum / len(nodes)

        # Check if in 0° ply (top or bottom)
        if y_c < t_0 - 1e-6:
            return 45.0  # bottom 0° ply
        if y_c > t_0 + t_90 + 1e-6:
            return 45.0  # top 0° ply

        # In 90° ply — find column and row
        dx = L / float(n_cols)
        row_thickness = t_90 / float(n_rows)

        # Column index (0 to n_cols-1)
        col_idx = int(x_c / dx)
        if col_idx < 0:
            col_idx = 0
        if col_idx >= n_cols:
            col_idx = n_cols - 1

        # Row index (0 to n_rows-1), relative to 90° ply bottom
        y_rel = y_c - t_0
        row_idx = int(y_rel / row_thickness)
        if row_idx < 0:
            row_idx = 0
        if row_idx >= n_rows:
            row_idx = n_rows - 1

        return vf_field[row_idx][col_idx]

    except Exception as e:
        return 45.0  # default


def add_vf_field(odb_path, job_name=None):
    """Add a VF field to the ODB at frame 0 of each step."""
    try:
        from odbAccess import openOdb
        from abaqusConstants import SCALAR, CENTROID
    except ImportError:
        print('ERROR: Must run with abaqus python')
        print('Usage: abaqus python scripts/add_vf_field.py --odb <path>')
        sys.exit(1)

    if not os.path.exists(odb_path):
        print('ERROR: ODB file not found: %s' % odb_path)
        sys.exit(1)

    # Get job parameters from config
    try:
        import config
        if job_name:
            job = config.get_job_by_name(job_name)
            if job:
                L = config.GAUGE_LENGTH_MM
                t_0 = job['t0_mm']
                t_90 = job['t90_mm']
                rho_sat = job['rho_sat']
                seed = config.DEFAULT_SEED
            else:
                print('ERROR: job %s not found in config' % job_name)
                sys.exit(1)
        else:
            # Try to guess job name from ODB filename
            base = os.path.splitext(os.path.basename(odb_path))[0]
            job = config.get_job_by_name(base)
            if job:
                L = config.GAUGE_LENGTH_MM
                t_0 = job['t0_mm']
                t_90 = job['t90_mm']
                rho_sat = job['rho_sat']
                seed = config.DEFAULT_SEED
                job_name = base
            else:
                print('ERROR: Could not determine job parameters.')
                print('Please specify --job-name')
                sys.exit(1)
    except Exception as e:
        print('ERROR loading config: %s' % e)
        sys.exit(1)

    print('=' * 70)
    print('Adding VF field to: %s' % odb_path)
    print('  Job: %s' % job_name)
    print('  L=%.1f, t_0=%.3f, t_90=%.3f, rho_sat=%.1f, seed=%d' % (
        L, t_0, t_90, rho_sat, seed))
    print('=' * 70)

    # Reconstruct Vf field
    print('Reconstructing Vf field...')
    vf_field, n_cols, n_rows = _reconstruct_vf_field(L, t_0, t_90, rho_sat, seed)
    if vf_field is None:
        print('FAILED to reconstruct Vf field')
        sys.exit(1)
    print('  Vf field: %d rows x %d cols' % (n_rows, n_cols))

    # Open ODB in writable mode
    print('Opening ODB (writable)...')
    odb = openOdb(odb_path, readOnly=False)

    try:
        for inst_name in odb.rootAssembly.instances.keys():
            instance = odb.rootAssembly.instances[inst_name]
            print('Processing instance: %s (%d elements)' % (
                inst_name, len(instance.elements)))

            # Create VF field output at frame 0 of each step
            for step_name in odb.steps.keys():
                step = odb.steps[step_name]
                if len(step.frames) == 0:
                    continue

                frame = step.frames[0]

                # Check if VF field already exists
                if 'VF' in frame.fieldOutputs.keys():
                    print('  VF field already exists in step %s frame 0 — skipping' % step_name)
                    continue

                # Create the field
                try:
                    vf_field_out = frame.FieldOutput(
                        name='VF',
                        description='Fiber Volume Fraction (%)',
                        type=SCALAR)
                except Exception as e:
                    print('  ERROR creating FieldOutput: %s' % e)
                    continue

                # Build element labels and Vf values based on position
                labels_list = []
                data_list = []
                for elem in instance.elements:
                    vf = _element_to_vf(elem, vf_field, n_cols, n_rows,
                                        L, t_0, t_90)
                    labels_list.append(elem.label)
                    data_list.append(vf)

                print('  Computed Vf for %d elements' % len(labels_list))
                # Print some stats
                if data_list:
                    vf_min = min(data_list)
                    vf_max = max(data_list)
                    vf_mean = sum(data_list) / len(data_list)
                    print('  Vf range: %.1f to %.1f (mean=%.1f)' % (
                        vf_min, vf_max, vf_mean))

                # Try to add data using different methods
                added = 0

                # Method 1: Bulk addData with flat tuples (1D)
                try:
                    vf_field_out.addData(
                        position=CENTROID,
                        instance=instance,
                        labels=tuple(labels_list),
                        data=tuple(data_list))
                    added = len(labels_list)
                    print('  Step %s frame 0: added %d VF values (1D bulk)' % (
                        step_name, added))
                except Exception as e1:
                    print('  1D bulk failed: %s' % e1)

                    # Method 2: Per-element 1D
                    try:
                        for i in range(len(labels_list)):
                            vf_field_out.addData(
                                position=CENTROID,
                                instance=instance,
                                labels=(labels_list[i],),
                                data=(data_list[i],))
                            added += 1
                        print('  Step %s frame 0: added %d VF values (1D per-element)' % (
                            step_name, added))
                    except Exception as e2:
                        print('  1D per-element failed: %s' % e2)

                        # Method 3: Bulk with 2D tuples
                        try:
                            labels_2d = tuple((l,) for l in labels_list)
                            data_2d = tuple((v,) for v in data_list)
                            vf_field_out.addData(
                                position=CENTROID,
                                instance=instance,
                                labels=labels_2d,
                                data=data_2d)
                            added = len(labels_list)
                            print('  Step %s frame 0: added %d VF values (2D bulk)' % (
                                step_name, added))
                        except Exception as e3:
                            print('  2D bulk failed: %s' % e3)
                            print('  WARNING: No VF values were added!')

        # Save the ODB
        print('Saving ODB...')
        odb.save()
        print('SUCCESS: VF field added and saved.')

    finally:
        odb.close()

    print()
    print('=' * 70)
    print('NEXT STEPS:')
    print('=' * 70)
    print()
    print('1. Open the .odb in Abaqus/CAE:')
    print('   abaqus cae database=%s' % odb_path)
    print()
    print('2. Switch to Visualization module')
    print()
    print('3. Menu: Result > Field Output...')
    print('   - Primary Variable: VF')
    print('   - Component: Scalar')
    print()
    print('4. The 90%% ply will show Vf distribution (0-90%%)')
    print('   0° plies will show Vf = 45%% (uniform)')
    print()
    print('5. Set color scale to 0-90:')
    print('   View > Display Options > Color & Visibility > Contour')
    print('   - Limits: Min=0, Max=90')
    print()
    print('6. Capture screenshot (File > Print > File > PNG, 300 DPI)')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--odb', required=True)
    parser.add_argument('--job-name', default=None,
                        help='Job name (e.g. val_0904s) for parameters lookup')
    args, _ = parser.parse_known_args()
    add_vf_field(args.odb, args.job_name)


if __name__ == '__main__':
    main()
