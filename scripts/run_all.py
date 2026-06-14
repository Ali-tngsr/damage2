# -*- coding: utf-8 -*-
"""
Convenience runner for the non-Abaqus utility scripts.

Python 2.7 compatible.
"""

from __future__ import division

import os
import sys
import csv

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
    out_dir = "results"
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)

    write_table1_csv(os.path.join(out_dir, "table1_transcribed.csv"))
    field = generate_vf_field(config.DEFAULT_N_COLS, config.DEFAULT_N_ROWS, config.DEFAULT_SEED)
    save_field_csv(field, os.path.join(out_dir, "vf_field_preview.csv"))
    print("Wrote preview CSV files to %s" % out_dir)


if __name__ == "__main__":
    main()
