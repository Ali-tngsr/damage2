# -*- coding: utf-8 -*-
"""
ODB post-processing for stress-strain, stiffness degradation, and crack density.

Run inside Abaqus:
    abaqus python postprocess_odb.py path/to/job.odb

Python 2.7 compatible.
"""

from __future__ import division

import os
import sys
import csv
import json

try:
    import numpy as np
except ImportError:
    np = None

try:
    from odbAccess import openOdb
except Exception:
    openOdb = None


def _mean_weighted(values, weights):
    if not values:
        return 0.0
    if np is not None:
        return float(np.dot(np.array(values, dtype=float), np.array(weights, dtype=float)) / sum(weights))
    return sum(v * w for v, w in zip(values, weights)) / float(sum(weights))


def _safe_get_field(frame, name):
    try:
        return frame.fieldOutputs[name]
    except Exception:
        return None


def _find_step(odb):
    if len(odb.steps.keys()) == 0:
        raise RuntimeError("ODB contains no steps.")
    if "Step-1" in odb.steps.keys():
        return odb.steps["Step-1"]
    return odb.steps[odb.steps.keys()[0]]


def _write_csv(path, rows, header):
    f = open(path, "w")
    try:
        writer = csv.writer(f)
        writer.writerow(header)
        for row in rows:
            writer.writerow(row)
    finally:
        f.close()


def _get_set_labels(odb, set_name):
    # Attempt to collect labels from the assembly set.
    root = odb.rootAssembly
    if set_name not in root.elementSets.keys():
        return set()
    elset = root.elementSets[set_name]
    labels = set()
    for e in elset.elements:
        labels.add(e.label)
    return labels


def postprocess(odb_path, out_dir="results"):
    if openOdb is None:
        raise RuntimeError("odbAccess is only available inside Abaqus Python.")

    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)

    odb = openOdb(path=odb_path, readOnly=True)
    try:
        step = _find_step(odb)

        # These set names should match the builder script.
        ply90_labels = _get_set_labels(odb, "PLY90")
        coh_labels = _get_set_labels(odb, "COH")

        # Fallbacks: if sets are missing, still collect global response.
        global_rows = []
        ply_rows = []
        crack_rows = []

        # Try to infer gauge length from summary JSON if present.
        summary_path = os.path.join(out_dir, "model_summary.json")
        gauge_length = 70.0
        if os.path.isfile(summary_path):
            try:
                summary = json.load(open(summary_path, "r"))
                gauge_length = float(summary.get("gauge_length_mm", gauge_length))
            except Exception:
                pass

        for frame_idx, frame in enumerate(step.frames):
            time_val = float(frame.frameValue)

            rf = _safe_get_field(frame, "RF")
            u = _safe_get_field(frame, "U")
            s = _safe_get_field(frame, "S")
            sdeg = _safe_get_field(frame, "SDV1")  # if a user SDV is used for damage
            if sdeg is None:
                sdeg = _safe_get_field(frame, "SDEG")

            # Global force from right-edge reaction force if available.
            total_rf1 = 0.0
            if rf is not None:
                for v in rf.values:
                    try:
                        total_rf1 += float(v.data[0])
                    except Exception:
                        pass

            # Global strain from right-edge displacement if available.
            avg_u1 = 0.0
            n_u = 0
            if u is not None:
                for v in u.values:
                    try:
                        avg_u1 += float(v.data[0])
                        n_u += 1
                    except Exception:
                        pass
            if n_u > 0:
                avg_u1 /= float(n_u)

            eng_strain = avg_u1 / gauge_length if gauge_length > 0.0 else 0.0
            # Nominal engineering stress requires section area; use unit thickness normalization if unknown.
            nominal_stress = total_rf1

            global_rows.append([frame_idx, time_val, eng_strain, nominal_stress])

            # 90-degree ply averaged S11
            s11_vals = []
            vols = []
            if s is not None:
                for v in s.values:
                    try:
                        label = v.elementLabel
                    except Exception:
                        continue
                    if ply90_labels and label not in ply90_labels:
                        continue
                    try:
                        s11_vals.append(float(v.data[0]))
                        vols.append(1.0)
                    except Exception:
                        pass
            ply_avg = _mean_weighted(s11_vals, vols)
            ply_rows.append([frame_idx, time_val, eng_strain, ply_avg])

            # Crack count: count cohesive labels with damage > 0.5
            crack_count = 0
            if sdeg is not None:
                for v in sdeg.values:
                    try:
                        label = v.elementLabel
                    except Exception:
                        continue
                    if coh_labels and label not in coh_labels:
                        continue
                    val = None
                    try:
                        val = v.data
                    except Exception:
                        val = None
                    if val is None:
                        continue
                    # Accept scalar or tuple.
                    if hasattr(val, "__len__"):
                        dmg = float(val[0])
                    else:
                        dmg = float(val)
                    if dmg > 0.5:
                        crack_count += 1
            crack_rows.append([frame_idx, time_val, eng_strain, crack_count])

        _write_csv(os.path.join(out_dir, "global_stress_strain.csv"),
                   global_rows, ["frame", "time", "strain", "nominal_stress"])
        _write_csv(os.path.join(out_dir, "ply90_stress.csv"),
                   ply_rows, ["frame", "time", "strain", "avg_s11_ply90"])
        _write_csv(os.path.join(out_dir, "crack_count.csv"),
                   crack_rows, ["frame", "time", "strain", "crack_count"])

        # Derived stiffness degradation curve from ply average slope.
        stiff_rows = []
        if len(ply_rows) >= 2:
            e0 = ply_rows[1][3] if ply_rows[1][3] != 0 else 1.0
            for row in ply_rows:
                norm_e = row[3] / e0 if e0 != 0 else 0.0
                stiff_rows.append([row[0], row[1], row[2], norm_e])
        _write_csv(os.path.join(out_dir, "normalized_stiffness.csv"),
                   stiff_rows, ["frame", "time", "strain", "E90_over_E0"])

        print("Post-processing complete.")
        print("Outputs written to: %s" % out_dir)
    finally:
        odb.close()


def main():
    if len(sys.argv) < 2:
        print("Usage: abaqus python postprocess_odb.py path/to/job.odb [out_dir]")
        sys.exit(1)
    odb_path = sys.argv[1]
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "results"
    postprocess(odb_path, out_dir=out_dir)


if __name__ == "__main__":
    main()
