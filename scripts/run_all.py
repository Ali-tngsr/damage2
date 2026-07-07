# -*- coding: utf-8 -*-
"""
Convenience runner for the non-Abaqus utility scripts.

Generates:
  - data/table1_transcribed.csv   (re-transcribed Table 1 for sanity check)
  - results/vf_field_preview.csv  (sample Vf field for visual inspection)

Python 2.7 compatible.
"""

from __future__ import division

import os
import sys
import csv

# Resolve paths relative to repo root so the script works from any CWD
try:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
REPO_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, '..'))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import config
from material_table import as_csv_rows
from vf_field import generate_vf_field, save_field_csv


def write_table1_csv(path):
    f = open(path, "w")
    try:
        writer = csv.writer(f)
        writer.writerow(["Vf_percent", "E11_GPa", "nu12", "E22_GPa", "nu23", "YT_MPa", "G12_GPa", "G23_GPa"])
        for row in as_csv_rows():
            writer.writerow(row)
    finally:
        f.close()


def main():
    data_dir = os.path.join(REPO_DIR, 'data')
    results_dir = os.path.join(REPO_DIR, 'results')
    for d in (data_dir, results_dir):
        if not os.path.isdir(d):
            os.makedirs(d)

    table1_path = os.path.join(data_dir, "table1_transcribed.csv")
    write_table1_csv(table1_path)
    print("Wrote: %s" % table1_path)

    field = generate_vf_field(config.DEFAULT_N_COLS, config.DEFAULT_N_ROWS, config.DEFAULT_SEED)
    vf_path = os.path.join(results_dir, "vf_field_preview.csv")
    save_field_csv(field, vf_path)
    print("Wrote: %s" % vf_path)

    print("\nVf field shape: %d rows x %d cols (seed=%d)" % (
        config.DEFAULT_N_ROWS, config.DEFAULT_N_COLS, config.DEFAULT_SEED))


if __name__ == "__main__":
    main()
