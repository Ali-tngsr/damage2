# -*- coding: utf-8 -*-
"""Diagnostic script: inspect what's actually inside an ODB file.

Usage:
    abaqus python scripts/diagnose_odb.py --odb abaqus_jobs/val_090s.odb

This script prints:
  - All instance names
  - All element sets on each instance (with element counts)
  - Element type distribution (CPS4R vs COH2D4 vs other)
  - Cohesive section assignment status
  - Step info and frame counts
  - Field outputs available in the last frame
  - Sample SDEG values from cohesive elements (if any)

Python 2.7 compatible.
"""
from __future__ import print_function

import argparse
import os
import sys


def _safe_get(d, key):
    if d is None:
        return None
    if key in d.keys():
        return d[key]
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--odb', required=True)
    args, _ = parser.parse_known_args()

    try:
        from odbAccess import openOdb
    except ImportError:
        print('ERROR: Must run with abaqus python')
        sys.exit(1)

    if not os.path.exists(args.odb):
        print('ERROR: ODB file not found: %s' % args.odb)
        sys.exit(1)

    print('=' * 70)
    print('ODB DIAGNOSTIC: %s' % args.odb)
    print('=' * 70)

    odb = openOdb(args.odb, readOnly=True)
    try:
        # =====================================================================
        # 1. Assembly instances
        # =====================================================================
        print('\n--- INSTANCES ---')
        instances = odb.rootAssembly.instances
        for name in instances.keys():
            inst = instances[name]
            n_nodes = len(inst.nodes)
            n_elements = len(inst.elements)
            print('  %s: %d nodes, %d elements' % (name, n_nodes, n_elements))

        # =====================================================================
        # 2. Element sets on each instance
        # =====================================================================
        print('\n--- ELEMENT SETS ---')
        for name in instances.keys():
            inst = instances[name]
            print('\n  Instance: %s' % name)
            for set_name in inst.elementSets.keys():
                eset = inst.elementSets[set_name]
                # Count elements
                try:
                    n = len(eset.elements)
                except Exception:
                    n = '?'
                print('    %s: %s elements' % (set_name, n))

        # Also check assembly-level sets
        print('\n  Assembly-level sets:')
        for set_name in odb.rootAssembly.elementSets.keys():
            eset = odb.rootAssembly.elementSets[set_name]
            try:
                n = len(eset.elements)
            except Exception:
                n = '?'
            print('    %s: %s elements' % (set_name, n))

        # =====================================================================
        # 3. Element type distribution
        # =====================================================================
        print('\n--- ELEMENT TYPE DISTRIBUTION ---')
        for name in instances.keys():
            inst = instances[name]
            type_counts = {}
            for elem in inst.elements:
                etype = str(elem.type)
                if etype in type_counts:
                    type_counts[etype] += 1
                else:
                    type_counts[etype] = 1
            print('\n  Instance: %s' % name)
            for etype, count in sorted(type_counts.items()):
                print('    %s: %d elements' % (etype, count))

        # =====================================================================
        # 4. Section assignments (if accessible)
        # =====================================================================
        print('\n--- SECTION ASSIGNMENT CHECK ---')
        # Section assignments are stored at the part level, not directly in ODB
        # But we can check element type as a proxy:
        #   - CPS4R = continuum (plane stress)
        #   - COH2D4 = cohesive
        # If there are COH2D4 elements, they should have a cohesive section
        for name in instances.keys():
            inst = instances[name]
            has_cohesive = False
            for elem in inst.elements:
                if str(elem.type) == 'COH2D4':
                    has_cohesive = True
                    break
            print('  Instance %s: has COH2D4 elements = %s' % (name, has_cohesive))

        # =====================================================================
        # 5. Steps and frames
        # =====================================================================
        print('\n--- STEPS ---')
        for step_name in odb.steps.keys():
            step = odb.steps[step_name]
            print('  Step: %s' % step_name)
            print('    Frames: %d' % len(step.frames))
            print('    Total time: %s' % step.totalTime)
            print('    Time period: %s' % step.timePeriod)
            if len(step.frames) > 0:
                last_frame = step.frames[-1]
                print('    Last frame value: %s' % last_frame.frameValue)
                print('    Last frame description: %s' % last_frame.description)

        # =====================================================================
        # 6. Field outputs in last frame
        # =====================================================================
        print('\n--- FIELD OUTPUTS (last frame) ---')
        for step_name in odb.steps.keys():
            step = odb.steps[step_name]
            if len(step.frames) == 0:
                continue
            last_frame = step.frames[-1]
            print('  Step %s, frame %d:' % (step_name, len(step.frames) - 1))
            for fo_name in last_frame.fieldOutputs.keys():
                fo = last_frame.fieldOutputs[fo_name]
                print('    %s: %d values' % (fo_name, len(fo.values)))

        # =====================================================================
        # 7. SDEG values from cohesive elements
        # =====================================================================
        print('\n--- SDEG CHECK (last frame) ---')
        for step_name in odb.steps.keys():
            step = odb.steps[step_name]
            if len(step.frames) == 0:
                continue
            last_frame = step.frames[-1]
            if 'SDEG' not in last_frame.fieldOutputs.keys():
                print('  No SDEG field in step %s' % step_name)
                continue

            sdeg_field = last_frame.fieldOutputs['SDEG']
            print('  Step %s: SDEG has %d values' % (step_name, len(sdeg_field.values)))

            # Build a set of COH2D4 element labels per instance
            # (SDEG is only meaningful for cohesive elements)
            coh2d4_labels_per_instance = {}
            for inst_name in instances.keys():
                inst = instances[inst_name]
                labels = set()
                try:
                    for elem in inst.elements:
                        if str(elem.type).upper() == 'COH2D4':
                            labels.add(elem.label)
                except Exception:
                    pass
                coh2d4_labels_per_instance[inst_name] = labels

            # Collect SDEG stats (only from COH2D4 elements)
            sdeg_values = []
            try:
                for value in sdeg_field.values:
                    label = value.elementLabel
                    inst_name = value.instance.name if value.instance else None
                    if inst_name and inst_name in coh2d4_labels_per_instance:
                        if label not in coh2d4_labels_per_instance[inst_name]:
                            continue
                    try:
                        sdeg_values.append(float(value.data))
                    except (TypeError, ValueError):
                        pass
            except Exception as e:
                print('  Note: SDEG read failed for some elements: %s' % e)

            if sdeg_values:
                print('    (only counting COH2D4 elements)')
                print('    count: %d' % len(sdeg_values))
                print('    min: %.6f' % min(sdeg_values))
                print('    max: %.6f' % max(sdeg_values))
                print('    mean: %.6f' % (sum(sdeg_values) / len(sdeg_values)))
                # Count damaged
                damaged = sum(1 for v in sdeg_values if v >= 0.95)
                partial = sum(1 for v in sdeg_values if 0.0 < v < 0.95)
                print('    damaged (SDEG >= 0.95): %d' % damaged)
                print('    partially damaged (0 < SDEG < 0.95): %d' % partial)
                print('    untouched (SDEG == 0): %d' % sum(1 for v in sdeg_values if v == 0.0))
            else:
                print('    No SDEG values from COH2D4 elements')

        # =====================================================================
        # 8. STATUS field (cohesive element status)
        # =====================================================================
        print('\n--- STATUS CHECK (last frame) ---')
        for step_name in odb.steps.keys():
            step = odb.steps[step_name]
            if len(step.frames) == 0:
                continue
            last_frame = step.frames[-1]
            if 'STATUS' not in last_frame.fieldOutputs.keys():
                print('  No STATUS field in step %s' % step_name)
                continue

            status_field = last_frame.fieldOutputs['STATUS']
            print('  Step %s: STATUS has %d values' % (step_name, len(status_field.values)))

            # Reuse coh2d4_labels_per_instance
            status_values = []
            try:
                for value in status_field.values:
                    label = value.elementLabel
                    inst_name = value.instance.name if value.instance else None
                    if inst_name and inst_name in coh2d4_labels_per_instance:
                        if label not in coh2d4_labels_per_instance[inst_name]:
                            continue
                    try:
                        status_values.append(float(value.data))
                    except (TypeError, ValueError):
                        pass
            except Exception as e:
                print('  Note: STATUS read failed for some elements: %s' % e)

            if status_values:
                print('    (only counting COH2D4 elements)')
                open_count = sum(1 for v in status_values if v < 1.0)
                closed_count = sum(1 for v in status_values if v >= 1.0)
                print('    open (STATUS < 1): %d' % open_count)
                print('    closed (STATUS >= 1): %d' % closed_count)

    finally:
        odb.close()

    print('\n' + '=' * 70)
    print('DIAGNOSTIC COMPLETE')
    print('=' * 70)


if __name__ == '__main__':
    main()
