# -*- coding: utf-8 -*-
"""Extract stress-strain, stiffness degradation, and crack density from Abaqus ODB.

Produces a CSV file with all data needed to reproduce paper Figs. 5, 9, 10, 11.

Usage (inside Abaqus Python environment):
    abaqus python scripts/postprocess_odb.py --odb path/to/job.odb
    abaqus python scripts/postprocess_odb.py --odb abaqus_jobs/val_090s.odb \\
        --output results/val_090s_summary.csv --job-name val_090s

CSV columns produced:
    frame, frame_value, strain_pct,
    sigma90_volumetric_mpa,        # Fig. 9a, 10a — volumetric-averaged σ_x⁹⁰
    global_stress_mpa,             # Fig. 5a — total reaction force / area
    E90_normalized,                # Fig. 5b, 9b, 10b — E90/E90°
    crack_count,                   # number of fully-propagated cracks
    normalized_crack_density,      # Fig. 11a, 11b — crack_count / rho_sat / t90 / L

Python 2.7 compatible (uses pure-python math, no numpy dependency).
"""
from __future__ import print_function

import argparse
import csv
import math
import os
import sys

# Resolve paths so config can be imported
try:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
REPO_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, '..'))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

# Abaqus odbAccess — only available inside `abaqus python`
try:
    from odbAccess import openOdb
    HAS_ODB_ACCESS = True
except ImportError:
    HAS_ODB_ACCESS = False

# Instance and set names — must match what build_mesoscale_model.py creates
INSTANCE_NAME = 'Specimen_Inst'
STEP_NAME = 'Step-1'
PLY90_SET_NAME = 'PLY90_FACES'
CRACK_SET_NAME = 'CRACK_PATHS'      # set by Cohesive_Mat2.create_crack_paths_set
POTENTIAL_CRACK_EDGES_SET = 'Potential_Crack_Edges'  # set by build_mesoscale_model

# Crack-counting threshold: a crack is "fully propagated" when SDEG >= this value
SDEG_FULLY_DAMAGED_THRESHOLD = 0.95


# =============================================================================
# Helper functions
# =============================================================================

def _safe_get(dictionary, key):
    if dictionary is None:
        return None
    if key in dictionary.keys():
        return dictionary[key]
    return None


def _element_label_set(element_set):
    """Return a Python set of element labels from an Abaqus element set."""
    labels = set()
    if element_set is None:
        return labels
    for element in element_set.elements:
        labels.add(element.label)
    return labels


def _compute_element_volumes(instance, element_labels):
    """Estimate element volumes from nodal coordinates (CPS4R = 4-node quad).

    For 2D plane-stress elements, "volume" = area × unit thickness (1 mm).
    So we just compute the area of each quadrilateral.

    Uses the shoelace formula on the 4 nodes.
    """
    volumes = {}
    if not element_labels:
        return volumes

    for label in element_labels:
        try:
            elem = instance.getElementFromLabel(label)
            nodes = elem.getNodes()
            if len(nodes) < 3:
                continue
            # Shoelace formula on first 4 nodes (CPS4R is quad)
            coords = [(n.coordinates[0], n.coordinates[1]) for n in nodes[:4]]
            n_pts = len(coords)
            area2 = 0.0
            for i in range(n_pts):
                x1, y1 = coords[i]
                x2, y2 = coords[(i + 1) % n_pts]
                area2 += (x1 * y2 - x2 * y1)
            area = abs(area2) * 0.5
            volumes[label] = area
        except Exception:
            volumes[label] = 1.0  # fallback — uniform weighting
    return volumes


def _volumetric_average_stress(stress_field, element_labels, element_volumes):
    """Compute volumetric-averaged S11 (sigma_x) over the 90° ply elements.

    Formula (paper §3.3):
        σ̄_x = Σ σ_x^i × v^i / Σ v^i
    """
    if not element_labels:
        return 0.0
    numerator = 0.0
    denominator = 0.0
    for value in stress_field.values:
        label = value.elementLabel
        if label not in element_labels:
            continue
        sigma_x = float(value.data[0])  # S11 = σ_x in 2D x-y plane
        vol = element_volumes.get(label, 1.0)
        numerator += sigma_x * vol
        denominator += vol
    if denominator == 0.0:
        return 0.0
    return numerator / denominator


def _total_reaction_force(rf_field, direction=0):
    """Sum reaction forces in given direction (default: x = u1)."""
    total = 0.0
    for value in rf_field.values:
        if len(value.data) > direction:
            total += float(value.data[direction])
    return total


def _count_cracks(sdeg_field, crack_labels, instance=None, threshold=SDEG_FULLY_DAMAGED_THRESHOLD):
    """Count fully-propagated cracks.

    A crack is counted when SDEG >= threshold across all cohesive elements in
    a single crack-path column. Since each column is one cohesive element row
    through the 90° ply thickness, we count unique columns where ALL cohesive
    elements are fully damaged.

    Simplification: count individual cohesive elements with SDEG >= threshold
    as a proxy for cracks. Each crack path has 5 cohesive elements (one per
    through-thickness cell), so divide by 5.

    Returns: (crack_count, total_cohesive_elements)
    """
    if not crack_labels or sdeg_field is None:
        return 0, 0

    # Build a set of COH2D4 element labels if instance is provided
    # (we only want to read SDEG/STATUS/DMICRT from cohesive elements,
    # because Abaqus throws errors when reading these fields from
    # continuum elements like CPS4R)
    coh2d4_labels = None
    if instance is not None:
        coh2d4_labels = set()
        try:
            for elem in instance.elements:
                if str(elem.type).upper() == 'COH2D4':
                    coh2d4_labels.add(elem.label)
        except Exception:
            coh2d4_labels = None

    damaged_count = 0
    total_count = 0
    for value in sdeg_field.values:
        label = value.elementLabel
        # Filter: only process elements that are in crack_labels AND (if available) are COH2D4
        if label not in crack_labels:
            continue
        if coh2d4_labels is not None and label not in coh2d4_labels:
            continue
        total_count += 1
        try:
            sdeg_val = float(value.data)
        except (TypeError, ValueError):
            continue
        if sdeg_val >= threshold:
            damaged_count += 1

    # Each crack path has 5 cohesive elements (N_THROUGH_THICKNESS_CELLS = 5)
    cracks = int(math.floor(damaged_count / 5.0)) if damaged_count > 0 else 0
    return cracks, total_count


# =============================================================================
# Main extraction function
# =============================================================================

def extract_results(odb_path, output_csv=None, job_name=None,
                    L=70.0, width=20.0, t90_mm=0.255, rho_sat=8.0):
    """Extract per-frame results from an ODB file.

    Parameters
    ----------
    odb_path : str
        Path to .odb file
    output_csv : str, optional
        Output CSV path. Defaults to <odb_name>_summary.csv
    job_name : str, optional
        Job name for logging (e.g. 'val_090s')
    L : float
        Specimen gauge length (mm)
    width : float
        Specimen width (mm) — used for global stress = F / (width * thickness)
    t90_mm : float
        90° ply thickness (mm) — used for crack density normalization
    rho_sat : float
        Crack saturation density (cracks/mm) — used for normalized crack density
    """
    if not HAS_ODB_ACCESS:
        print('ERROR: Abaqus Python environment required to read .odb files.')
        print('Run this as: abaqus python scripts/postprocess_odb.py --odb ...')
        return None

    if output_csv is None:
        base = os.path.splitext(os.path.basename(odb_path))[0]
        output_csv = os.path.join(REPO_DIR, 'results', base + '_summary.csv')
    if not os.path.isdir(os.path.dirname(output_csv)):
        os.makedirs(os.path.dirname(output_csv))

    if job_name is None:
        job_name = os.path.splitext(os.path.basename(odb_path))[0]

    print('=' * 70)
    print('POST-PROCESSING: %s' % job_name)
    print('=' * 70)
    print('  ODB:        %s' % odb_path)
    print('  Output CSV: %s' % output_csv)
    print('  L=%.1f mm, width=%.1f mm, t90=%.3f mm, rho_sat=%.1f /mm' % (
        L, width, t90_mm, rho_sat))
    print('=' * 70)

    print('Opening ODB...')
    odb = openOdb(odb_path, readOnly=True)

    try:
        step = odb.steps[STEP_NAME]

        # =====================================================================
        # Auto-detect instance name (it may differ between GUI and noGUI setup)
        # =====================================================================
        instances = odb.rootAssembly.instances
        instance = None

        # Strategy 1: try the expected name
        if INSTANCE_NAME in instances.keys():
            instance = instances[INSTANCE_NAME]
            print('  Found instance: %s' % INSTANCE_NAME)
        else:
            # Strategy 2: list all instances and pick the one with PLY90_FACES set
            print('  Instance "%s" not found. Available instances:' % INSTANCE_NAME)
            for name in instances.keys():
                print('    - %s' % name)

            # Try to find an instance that contains PLY90_FACES set
            for name in instances.keys():
                inst = instances[name]
                if PLY90_SET_NAME in inst.elementSets.keys() or \
                   PLY90_SET_NAME.upper() in [s.upper() for s in inst.elementSets.keys()]:
                    instance = inst
                    print('  Auto-selected instance: %s (has %s set)' % (name, PLY90_SET_NAME))
                    break

            # Strategy 3: if only one instance, use it
            if instance is None and len(instances.keys()) == 1:
                instance = instances[instances.keys()[0]]
                print('  Auto-selected only instance: %s' % instances.keys()[0])

            # Strategy 4: pick the first non-assembly instance
            if instance is None:
                for name in instances.keys():
                    if not name.startswith('ASSEMBLY'):
                        instance = instances[name]
                        print('  Auto-selected instance: %s' % name)
                        break

        if instance is None:
            raise KeyError('No suitable instance found in ODB. Available: %s'
                          % ', '.join(instances.keys()))

        # =====================================================================
        # Auto-detect set names (case-insensitive fallback)
        # =====================================================================
        ply90_set = None
        for sname in (PLY90_SET_NAME, PLY90_SET_NAME.upper(), PLY90_SET_NAME.lower(),
                      'PLY90', 'PLY_90_FACES', 'PLY90FACES'):
            ply90_set = _safe_get(instance.elementSets, sname)
            if ply90_set is not None:
                if sname != PLY90_SET_NAME:
                    print('  Note: using set "%s" instead of "%s"' % (sname, PLY90_SET_NAME))
                break

        crack_set = None
        for sname in (CRACK_SET_NAME, POTENTIAL_CRACK_EDGES_SET,
                      CRACK_SET_NAME.upper(), POTENTIAL_CRACK_EDGES_SET.upper(),
                      'CRACK_PATHS', 'POTENTIAL_CRACK_EDGES'):
            crack_set = _safe_get(instance.elementSets, sname)
            if crack_set is not None:
                if sname not in (CRACK_SET_NAME, POTENTIAL_CRACK_EDGES_SET):
                    print('  Note: using crack set "%s"' % sname)
                break

        # Also check the assembly-level sets (sometimes sets are defined there)
        if ply90_set is None:
            for sname in (PLY90_SET_NAME, PLY90_SET_NAME.upper()):
                ply90_set = _safe_get(odb.rootAssembly.elementSets, sname)
                if ply90_set is not None:
                    print('  Note: using assembly-level set "%s"' % sname)
                    break

        if crack_set is None:
            for sname in (CRACK_SET_NAME, POTENTIAL_CRACK_EDGES_SET):
                crack_set = _safe_get(odb.rootAssembly.elementSets, sname)
                if crack_set is not None:
                    print('  Note: using assembly-level crack set "%s"' % sname)
                    break

        ply90_labels = _element_label_set(ply90_set)
        crack_labels = _element_label_set(crack_set)

        print('  Ply-90 elements: %d' % len(ply90_labels))
        print('  Cohesive (crack) elements: %d' % len(crack_labels))
        if len(ply90_labels) == 0:
            print('  WARNING: No PLY90 elements found. Set name may differ.')
            print('  Available element sets on instance:')
            for sname in instance.elementSets.keys():
                print('    - %s' % sname)

        # Pre-compute volumes for volumetric averaging (one-time cost)
        print('  Computing element volumes...')
        ply90_volumes = _compute_element_volumes(instance, ply90_labels)

        # Identify initial stiffness E90° (from first frame, near-zero strain)
        rows = []
        E90_initial = None
        cross_section_area = width * t90_mm  # for [0/90/0] with single 90° ply

        n_frames = len(step.frames)
        print('  Frames to process: %d' % n_frames)
        print('-' * 70)

        for frame_idx, frame in enumerate(step.frames):
            frame_value = float(frame.frameValue)

            # Convert frame value to strain
            # Abaqus static step with displacement control: frameValue = time fraction
            # Final strain = MAX_ENGINEERING_STRAIN (2.5%)
            # So strain = frame_value * 0.025
            strain = frame_value * 0.025
            strain_pct = strain * 100.0

            # ---- Volumetric-averaged σ_x⁹⁰ ----
            sigma90_vol = 0.0
            if 'S' in frame.fieldOutputs.keys():
                stress_field = frame.fieldOutputs['S']
                sigma90_vol = _volumetric_average_stress(
                    stress_field, ply90_labels, ply90_volumes)

            # ---- Global stress from reaction force ----
            global_stress = 0.0
            if 'RF' in frame.fieldOutputs.keys():
                rf_field = frame.fieldOutputs['RF']
                rf_total = _total_reaction_force(rf_field, direction=0)
                # Cross-section for global stress: width × total_thickness
                # Use width × t90 as approximation for 90° ply stress contribution
                if cross_section_area > 0:
                    global_stress = rf_total / cross_section_area

            # ---- Crack counting ----
            crack_count = 0
            total_cohesive = 0
            if 'SDEG' in frame.fieldOutputs.keys():
                try:
                    sdeg_field = frame.fieldOutputs['SDEG']
                    crack_count, total_cohesive = _count_cracks(
                        sdeg_field, crack_labels, instance=instance)
                except Exception as e:
                    if frame_idx == n_frames - 1:
                        print('  Note: SDEG read failed: %s' % e)
                    crack_count = 0
                    total_cohesive = 0

            # ---- Normalized crack density ----
            # Paper: ρ_norm = (number of cracks) / (ρ_sat × L)
            # Since the model uses rho_sat * L crack paths, the max possible
            # crack count is rho_sat * L, so this normalizes to [0, 1].
            norm_crack_density = 0.0
            if rho_sat > 0 and L > 0:
                norm_crack_density = crack_count / (rho_sat * L)

            # ---- Store row ----
            row = {
                'frame': frame_idx,
                'frame_value': frame_value,
                'strain': strain,
                'strain_pct': strain_pct,
                'sigma90_volumetric_mpa': sigma90_vol,
                'global_stress_mpa': global_stress,
                'crack_count': crack_count,
                'normalized_crack_density': norm_crack_density,
                'total_cohesive_elements': total_cohesive,
            }
            rows.append(row)

            # Capture initial stiffness from low-strain region
            if E90_initial is None and strain > 0.001 and strain < 0.005:
                # E90 = σ_x⁹⁰ / ε_x at small strain (before first crack)
                if strain > 0 and sigma90_vol > 0:
                    E90_initial = sigma90_vol / strain

            # Progress log
            if (frame_idx + 1) % 20 == 0 or frame_idx == 0 or frame_idx == n_frames - 1:
                print('  Frame %3d/%d: ε=%5.2f%%  σ90=%6.2f MPa  cracks=%3d' % (
                    frame_idx + 1, n_frames, strain_pct, sigma90_vol, crack_count))

        # ---- Compute normalized stiffness E90/E90° for each frame ----
        if E90_initial is None and len(rows) > 1:
            # Fallback: use secant stiffness between first two frames
            r0, r1 = rows[0], rows[1]
            d_eps = r1['strain'] - r0['strain']
            d_sig = r1['sigma90_volumetric_mpa'] - r0['sigma90_volumetric_mpa']
            if d_eps > 0:
                E90_initial = d_sig / d_eps

        print('-' * 70)
        print('  Initial E90 (secant, ε<0.5%%): %.3f MPa' % (E90_initial or 0.0))

        # Compute normalized stiffness via numerical differentiation
        # E90(ε) = dσ90/dε at each frame (using central difference)
        for i, row in enumerate(rows):
            if i == 0:
                d_eps = rows[1]['strain'] - rows[0]['strain']
                d_sig = rows[1]['sigma90_volumetric_mpa'] - rows[0]['sigma90_volumetric_mpa']
            elif i == len(rows) - 1:
                d_eps = rows[i]['strain'] - rows[i - 1]['strain']
                d_sig = rows[i]['sigma90_volumetric_mpa'] - rows[i - 1]['sigma90_volumetric_mpa']
            else:
                d_eps = rows[i + 1]['strain'] - rows[i - 1]['strain']
                d_sig = rows[i + 1]['sigma90_volumetric_mpa'] - rows[i - 1]['sigma90_volumetric_mpa']

            if d_eps > 0 and E90_initial and E90_initial > 0:
                E90_tangent = d_sig / d_eps
                row['E90_normalized'] = E90_tangent / E90_initial
            else:
                row['E90_normalized'] = 1.0

            # Clamp to [0, 1.2] for plotting sanity
            row['E90_normalized'] = max(0.0, min(1.2, row['E90_normalized']))

    finally:
        odb.close()

    # ---- Write CSV ----
    fieldnames = ['frame', 'frame_value', 'strain', 'strain_pct',
                  'sigma90_volumetric_mpa', 'global_stress_mpa',
                  'E90_normalized', 'crack_count', 'normalized_crack_density',
                  'total_cohesive_elements']

    with open(output_csv, 'w') as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator='\n')
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, '') for k in fieldnames})

    print()
    print('Wrote %d frames to: %s' % (len(rows), output_csv))
    print('Final state: %d cracks (normalized density = %.3f)' % (
        rows[-1]['crack_count'] if rows else 0,
        rows[-1]['normalized_crack_density'] if rows else 0.0))
    return output_csv


# =============================================================================
# CLI entry point
# =============================================================================

def _parse_cli(argv):
    """Parse command-line arguments. Works with `abaqus python` argv."""
    parser = argparse.ArgumentParser(description='Extract results from Abaqus ODB.')
    parser.add_argument('--odb', required=False, default=None,
                        help='Path to .odb file')
    parser.add_argument('--output', required=False, default=None,
                        help='Output CSV path (default: results/<odb_name>_summary.csv)')
    parser.add_argument('--job-name', required=False, default=None,
                        help='Job name (e.g. val_090s) — used to look up t90 from config')
    parser.add_argument('--L', type=float, default=70.0,
                        help='Gauge length in mm (default: 70)')
    parser.add_argument('--width', type=float, default=20.0,
                        help='Specimen width in mm (default: 20)')
    parser.add_argument('--t90', type=float, default=None,
                        help='90-ply thickness in mm (overrides config)')
    parser.add_argument('--rho-sat', type=float, default=8.0,
                        help='Crack saturation density in cracks/mm (default: 8)')

    args = parser.parse_args(argv[1:])

    # If job-name is given, look up t90 from config
    if args.job_name and args.t90 is None:
        try:
            import config
            job = config.get_job_by_name(args.job_name)
            if job:
                args.t90 = job['t90_mm']
                if args.t90 is None:
                    args.t90 = 0.255
                print('Looked up t90=%.3f mm for job %s' % (args.t90, args.job_name))
        except ImportError:
            pass

    if args.t90 is None:
        args.t90 = 0.255  # default to validation case

    return args


if __name__ == '__main__':
    args = _parse_cli(sys.argv)

    if args.odb is None:
        # Auto-detect ODB in abaqus_jobs/
        jobs_dir = os.path.join(REPO_DIR, 'abaqus_jobs')
        if os.path.isdir(jobs_dir):
            odbs = sorted([f for f in os.listdir(jobs_dir) if f.endswith('.odb')])
            if odbs:
                args.odb = os.path.join(jobs_dir, odbs[0])
                print('Auto-detected ODB: %s' % args.odb)
        if args.odb is None:
            print('ERROR: no --odb argument provided and no .odb files in abaqus_jobs/')
            sys.exit(1)

    extract_results(
        odb_path=args.odb,
        output_csv=args.output,
        job_name=args.job_name,
        L=args.L,
        width=args.width,
        t90_mm=args.t90,
        rho_sat=args.rho_sat,
    )
