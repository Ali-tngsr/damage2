# -*- coding: utf-8 -*-
"""Add a Vf (fiber volume fraction) field to an ODB for visualization.

This script creates a new field output called 'VF' in the ODB that
contains the fiber volume fraction of each element. This allows you to
plot Vf as a contour in Abaqus/CAE, giving a meaningful color map that
shows the stochastic Vf distribution in the 90° ply (like Fig. 4 of
the paper).

Usage:
    abaqus python scripts/add_vf_field.py --odb abaqus_jobs/val_0904s.odb

After running this script:
1. Open the .odb in Abaqus/CAE (Visualization module)
2. Result → Field Output → select "VF"
3. The 90° ply will show Vf distribution (0-90%)
4. 0° plies will show Vf = 45% (uniform)

Python 2.7 compatible (runs inside abaqus python).
"""
from __future__ import print_function

import argparse
import os
import sys
import math


def _parse_vf_from_material_name(mat_name):
    """Extract Vf value from material name like 'Mat_90deg_Vf45.0' or 'Mat_0deg_Vf45'.

    Returns the Vf as a float, or None if it can't be parsed.
    """
    # Look for 'Vf' followed by a number
    if 'Vf' not in mat_name:
        return None
    try:
        # Split on 'Vf' and take the part after it
        parts = mat_name.split('Vf')
        if len(parts) >= 2:
            vf_str = parts[1].strip()
            # Remove any trailing characters that aren't digits or dot
            vf_clean = ''
            for c in vf_str:
                if c.isdigit() or c == '.' or c == '-':
                    vf_clean += c
                else:
                    break
            if vf_clean:
                return float(vf_clean)
    except (ValueError, IndexError):
        pass
    return None


def _get_element_vf(instance, element_label):
    """Get the Vf value for an element by looking up its material.

    Returns 45.0 as default for 0° plies (or if can't be determined).
    """
    try:
        elem = instance.getElementFromLabel(element_label)
        section = None
        try:
            section_assignment = elem.sectionAssignment
            if section_assignment:
                section = section_assignment.section
        except Exception:
            pass

        if section is None:
            # Try via the element's section category
            try:
                sec_cat = elem.sectionCategory
                if sec_cat:
                    # Default for 0° plies
                    return 45.0
            except Exception:
                pass
            return 45.0

        # Get material name from section
        try:
            material_name = section.material
            vf = _parse_vf_from_material_name(material_name)
            if vf is not None:
                return vf
        except Exception:
            pass

        return 45.0
    except Exception:
        return 45.0


def add_vf_field(odb_path):
    """Add a VF field to the ODB at frame 0 of each step."""
    try:
        from odbAccess import openOdb, Odb
        from abaqusConstants import SCALAR, CENTROID, INTEGRATION_POINT
    except ImportError:
        print('ERROR: Must run with abaqus python')
        print('Usage: abaqus python scripts/add_vf_field.py --odb <path>')
        sys.exit(1)

    if not os.path.exists(odb_path):
        print('ERROR: ODB file not found: %s' % odb_path)
        sys.exit(1)

    print('=' * 70)
    print('Adding VF field to: %s' % odb_path)
    print('=' * 70)

    # Open ODB in writable mode (NOT readOnly)
    print('Opening ODB (writable)...')
    odb = openOdb(odb_path, readOnly=False)

    try:
        # Build a mapping: element label -> Vf value
        # Do this once per instance
        for inst_name in odb.rootAssembly.instances.keys():
            instance = odb.rootAssembly.instances[inst_name]
            print('Processing instance: %s (%d elements)' % (
                inst_name, len(instance.elements)))

            # Build material lookup from section assignments
            section_to_vf = {}
            try:
                for sa in instance.sectionAssignments:
                    try:
                        sec = sa.section
                        mat_name = sec.material
                        vf = _parse_vf_from_material_name(mat_name)
                        if vf is None:
                            vf = 45.0  # default
                        section_to_vf[sec.name] = vf
                    except Exception:
                        pass
            except Exception:
                pass

            print('  Found %d sections with Vf mapping' % len(section_to_vf))

            # Build element label -> Vf map using section assignments
            element_vf = {}
            try:
                for sa in instance.sectionAssignments:
                    try:
                        sec = sa.section
                        vf = section_to_vf.get(sec.name, 45.0)
                        # Get elements in this section assignment's region
                        region = sa.region
                        if region is None:
                            continue
                        try:
                            elements = region.elements
                        except Exception:
                            continue
                        for elem in elements:
                            element_vf[elem.label] = vf
                    except Exception:
                        continue
            except Exception as e:
                print('  Note: section assignment lookup failed: %s' % e)

            # For any elements not mapped, default to 45.0
            for elem in instance.elements:
                if elem.label not in element_vf:
                    element_vf[elem.label] = 45.0

            print('  Mapped %d elements to Vf values' % len(element_vf))

            # Create VF field output at frame 0 of each step
            for step_name in odb.steps.keys():
                step = odb.steps[step_name]
                if len(step.frames) == 0:
                    continue

                # Use frame 0 (initial state)
                frame = step.frames[0]

                # Check if VF field already exists
                if 'VF' in frame.fieldOutputs.keys():
                    print('  VF field already exists in step %s frame 0 — skipping' % step_name)
                    continue

                # Create the field
                try:
                    vf_field = frame.FieldOutput(
                        name='VF',
                        description='Fiber Volume Fraction (%)',
                        type=SCALAR)
                except Exception as e:
                    print('  ERROR creating FieldOutput: %s' % e)
                    continue

                # Add values for each element using bulk addData
                # Build parallel arrays of labels and data
                labels_list = []
                data_list = []
                for elem in instance.elements:
                    vf = element_vf.get(elem.label, 45.0)
                    labels_list.append(elem.label)
                    data_list.append(vf)

                try:
                    vf_field.addData(
                        position=CENTROID,
                        instance=instance,
                        labels=tuple(labels_list),
                        data=tuple(data_list))
                    print('  Step %s frame 0: added %d VF values (bulk)' % (
                        step_name, len(labels_list)))
                except Exception as e1:
                    print('  Bulk addData failed: %s' % e1)
                    # Fallback: add per element
                    added = 0
                    for i, label in enumerate(labels_list):
                        try:
                            vf_field.addData(
                                position=CENTROID,
                                instance=instance,
                                labels=(label,),
                                data=(data_list[i],))
                            added += 1
                        except Exception:
                            pass
                    print('  Step %s frame 0: added %d VF values (per-element)' % (
                        step_name, added))

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
    args, _ = parser.parse_known_args()
    add_vf_field(args.odb)


if __name__ == '__main__':
    main()
