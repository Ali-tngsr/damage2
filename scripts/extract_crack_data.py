# -*- coding: utf-8 -*-
"""Extract crack morphology data from an ODB for Figure 6/7/8.

This script reads an ODB file and extracts:
  - Element positions (centroids)
  - SDEG values at the last frame
  - Element type (CPS4R vs COH2D4)
  - Damage status (cracked if SDEG >= threshold)

Output: a JSON file with crack positions and model outline.

Usage:
    abaqus python scripts/extract_crack_data.py --odb abaqus_jobs/val_090s.odb
    abaqus python scripts/extract_crack_data.py --odb abaqus_jobs/val_090s.odb --output results/val_090s_cracks.json

Python 2.7 compatible (runs inside abaqus python).
"""
from __future__ import print_function

import argparse
import json
import os
import sys
import math


def _element_centroid(elem):
    """Compute element centroid from node coordinates."""
    try:
        nodes = elem.getNodes()
        if not nodes:
            return (0.0, 0.0)
        x_sum = 0.0
        y_sum = 0.0
        for node in nodes:
            coords = node.coordinates
            x_sum += float(coords[0])
            y_sum += float(coords[1])
        return (x_sum / len(nodes), y_sum / len(nodes))
    except Exception:
        return (0.0, 0.0)


def _element_corners(elem):
    """Get element corner coordinates for drawing."""
    try:
        nodes = elem.getNodes()
        if not nodes:
            return []
        coords = [(float(n.coordinates[0]), float(n.coordinates[1])) for n in nodes]
        return coords
    except Exception:
        return []


def extract_crack_data(odb_path, output_path=None, threshold=0.95,
                       job_name=None):
    """Extract crack data from ODB and save as JSON."""
    try:
        from odbAccess import openOdb
    except ImportError:
        print('ERROR: Must run with abaqus python')
        print('Usage: abaqus python scripts/extract_crack_data.py --odb <path>')
        sys.exit(1)

    if not os.path.exists(odb_path):
        print('ERROR: ODB file not found: %s' % odb_path)
        sys.exit(1)

    if output_path is None:
        base = os.path.splitext(os.path.basename(odb_path))[0]
        results_dir = os.path.join(os.path.dirname(os.path.dirname(odb_path)), 'results')
        if not os.path.isdir(results_dir):
            os.makedirs(results_dir)
        output_path = os.path.join(results_dir, base + '_cracks.json')

    # Get job parameters from config for geometry
    L = 70.0
    total_thickness = 1.0
    t_0 = 0.25
    t_90 = 0.255
    try:
        SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
        if SCRIPT_DIR not in sys.path:
            sys.path.insert(0, SCRIPT_DIR)
        import config
        if job_name is None:
            base = os.path.splitext(os.path.basename(odb_path))[0]
            job_name = base
        job = config.get_job_by_name(job_name)
        if job:
            L = config.GAUGE_LENGTH_MM
            t_0 = job['t0_mm']
            t_90 = job['t90_mm']
            total_thickness = job['total_thickness_mm']
    except Exception as e:
        print('Note: could not load config, using defaults: %s' % e)

    print('=' * 70)
    print('Extracting crack data from: %s' % odb_path)
    print('  Output: %s' % output_path)
    print('  L=%.1f, t_0=%.3f, t_90=%.3f, total=%.3f' % (
        L, t_0, t_90, total_thickness))
    print('  Crack threshold: SDEG >= %.2f' % threshold)
    print('=' * 70)

    print('Opening ODB...')
    odb = openOdb(odb_path, readOnly=True)

    result = {
        'odb_path': odb_path,
        'job_name': job_name,
        'geometry': {
            'L': L,
            't_0': t_0,
            't_90': t_90,
            'total_thickness': total_thickness,
        },
        'threshold': threshold,
        'frames': [],
    }

    try:
        # Get all instances
        instances = odb.rootAssembly.instances
        if len(instances.keys()) == 0:
            print('ERROR: No instances in ODB')
            sys.exit(1)

        # Use first (or only) instance
        inst_name = instances.keys()[0]
        instance = instances[inst_name]
        print('Using instance: %s (%d elements)' % (inst_name, len(instance.elements)))

        # Build element type lookup
        element_types = {}
        for elem in instance.elements:
            element_types[elem.label] = str(elem.type)
        n_cohesive = sum(1 for t in element_types.values() if 'COH' in t.upper())
        n_continuum = sum(1 for t in element_types.values() if 'CPS' in t.upper() or 'CPE' in t.upper())
        print('  Continuum elements: %d' % n_continuum)
        print('  Cohesive elements: %d' % n_cohesive)

        # Process each step
        for step_name in odb.steps.keys():
            step = odb.steps[step_name]
            print('Step: %s (%d frames)' % (step_name, len(step.frames)))

            # Process all frames (or just key frames for Fig. 8)
            for frame_idx, frame in enumerate(step.frames):
                frame_value = float(frame.frameValue)
                strain = frame_value * 0.025  # assume max strain = 2.5%
                strain_pct = strain * 100.0

                # Get SDEG field
                sdeg_field = None
                if 'SDEG' in frame.fieldOutputs.keys():
                    sdeg_field = frame.fieldOutputs['SDEG']

                if sdeg_field is None:
                    continue

                # Build SDEG lookup: element label -> sdeg value
                sdeg_values = {}
                try:
                    for value in sdeg_field.values:
                        label = value.elementLabel
                        try:
                            sdeg_values[label] = float(value.data)
                        except (TypeError, ValueError):
                            pass
                except Exception as e:
                    print('  Note: SDEG read error at frame %d: %s' % (frame_idx, e))
                    continue

                # Identify cracked cohesive elements (SDEG >= threshold)
                cracked_elements = []
                partial_elements = []
                intact_elements = []

                for elem in instance.elements:
                    label = elem.label
                    etype = element_types.get(label, '')
                    if 'COH' not in etype.upper():
                        continue  # only cohesive elements have SDEG

                    sdeg = sdeg_values.get(label, 0.0)
                    corners = _element_corners(elem)
                    centroid = _element_centroid(elem)

                    if sdeg >= threshold:
                        cracked_elements.append({
                            'label': label,
                            'sdeg': sdeg,
                            'centroid': centroid,
                            'corners': corners,
                        })
                    elif sdeg > 0.01:
                        partial_elements.append({
                            'label': label,
                            'sdeg': sdeg,
                            'centroid': centroid,
                            'corners': corners,
                        })
                    else:
                        intact_elements.append({
                            'label': label,
                            'sdeg': sdeg,
                            'centroid': centroid,
                        })

                # Also get continuum element positions for outline
                continuum_elements = []
                for elem in instance.elements:
                    label = elem.label
                    etype = element_types.get(label, '')
                    if 'COH' in etype.upper():
                        continue
                    corners = _element_corners(elem)
                    if corners:
                        continuum_elements.append({
                            'label': label,
                            'corners': corners,
                        })

                frame_data = {
                    'frame_idx': frame_idx,
                    'frame_value': frame_value,
                    'strain': strain,
                    'strain_pct': strain_pct,
                    'n_cracked': len(cracked_elements),
                    'n_partial': len(partial_elements),
                    'n_intact_cohesive': len(intact_elements),
                    'n_continuum': len(continuum_elements),
                    'cracked_elements': cracked_elements,
                    'partial_elements': partial_elements,
                    'continuum_outline': continuum_elements[:200],  # limit for JSON size
                }
                result['frames'].append(frame_data)

                if frame_idx % 20 == 0 or frame_idx == len(step.frames) - 1:
                    print('  Frame %3d/%d: strain=%5.2f%%  cracked=%4d  partial=%4d' % (
                        frame_idx + 1, len(step.frames), strain_pct,
                        len(cracked_elements), len(partial_elements)))

    finally:
        odb.close()

    # Save JSON
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)

    print()
    print('=' * 70)
    print('SUCCESS: Crack data saved to %s' % output_path)
    print('=' * 70)
    print()
    print('Total frames: %d' % len(result['frames']))
    if result['frames']:
        last = result['frames'][-1]
        print('Last frame (strain=%.2f%%):' % last['strain_pct'])
        print('  Cracked cohesive elements: %d' % last['n_cracked'])
        print('  Partial damage: %d' % last['n_partial'])
        print('  Intact cohesive: %d' % last['n_intact_cohesive'])
        print('  Continuum elements: %d' % last['n_continuum'])
    print()
    print('Next: run plot_figure_06.py to generate the figure')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--odb', required=True)
    parser.add_argument('--output', default=None)
    parser.add_argument('--job-name', default=None)
    parser.add_argument('--threshold', type=float, default=0.95)
    args, _ = parser.parse_known_args()
    extract_crack_data(args.odb, args.output, args.threshold, args.job_name)


if __name__ == '__main__':
    main()
