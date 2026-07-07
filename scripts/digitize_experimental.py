# -*- coding: utf-8 -*-
"""Helper to load digitized experimental data from Fig. 5 of the paper.

The paper's Fig. 5 contains experimental stress-strain and stiffness-degradation
curves for [0/90]s, [0/902]s, [0/904]s laminates from Ref. [45]. To overlay
these on our model results, the user must digitize them ONCE using a free tool
like WebPlotDigitizer (https://automeris.io/WebPlotDigitizer/).

This script:
  1. Documents the digitization workflow
  2. Validates the CSV format
  3. Provides a template CSV

Usage:
    python3 scripts/digitize_experimental.py --check        # validate CSV format
    python3 scripts/digitize_experimental.py --template     # write template CSV

CSV format expected at data/experimental_fig5.csv:
    strain_pct, stress_090s, stress_0902s, stress_0904s, \
                E90norm_090s, E90norm_0902s, E90norm_0904s

Strain in percent (0-2.5), stress in MPa, E90_norm dimensionless (0-1).

Python 2.7 + 3 compatible.
"""
from __future__ import print_function

import argparse
import csv
import os
import sys


try:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
REPO_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, '..'))
DATA_DIR = os.path.join(REPO_DIR, 'data')
EXP_CSV_PATH = os.path.join(DATA_DIR, 'experimental_fig5.csv')


REQUIRED_COLUMNS = [
    'strain_pct',
    'stress_090s', 'stress_0902s', 'stress_0904s',
    'E90norm_090s', 'E90norm_0902s', 'E90norm_0904s',
]

# Approximate experimental data points from Fig. 5 of the paper
# (rough digitization — replace with precise values from WebPlotDigitizer)
TEMPLATE_ROWS = [
    # (strain%, stress_090s, stress_0902s, stress_0904s, E90n_090s, E90n_0902s, E90n_0904s)
    (0.0,    0.0,   0.0,   0.0,   1.00, 1.00, 1.00),
    (0.1,    5.0,   6.0,   7.0,   1.00, 1.00, 1.00),
    (0.2,   10.0,  12.0,  14.0,   1.00, 1.00, 1.00),
    (0.3,   15.0,  18.0,  21.0,   0.99, 0.99, 0.99),
    (0.35,  17.5,  21.0,  24.5,   0.97, 0.95, 0.93),  # first crack onset
    (0.4,   20.0,  23.5,  27.0,   0.92, 0.88, 0.83),
    (0.5,   22.0,  26.0,  30.0,   0.85, 0.78, 0.71),
    (0.6,   23.5,  28.0,  32.0,   0.78, 0.69, 0.60),
    (0.8,   26.0,  30.0,  34.0,   0.66, 0.55, 0.46),
    (1.0,   28.0,  31.0,  35.0,   0.55, 0.45, 0.38),
    (1.2,   29.0,  32.0,  36.0,   0.48, 0.39, 0.32),
    (1.5,   30.0,  32.5, 36.5,   0.42, 0.34, 0.28),
    (1.8,   30.5, 33.0,  37.0,   0.38, 0.31, 0.26),
    (2.0,   31.0, 33.0,  37.0,   0.35, 0.30, 0.24),
    (2.5,   31.5, 33.0,  37.0,   0.32, 0.30, 0.22),
]


def write_template():
    """Write template CSV with approximate digitized values."""
    if not os.path.isdir(DATA_DIR):
        os.makedirs(DATA_DIR)

    if os.path.exists(EXP_CSV_PATH):
        print('WARNING: %s already exists — backing up to .bak' % EXP_CSV_PATH)
        os.rename(EXP_CSV_PATH, EXP_CSV_PATH + '.bak')

    with open(EXP_CSV_PATH, 'w') as f:
        writer = csv.writer(f, lineterminator='\n')
        writer.writerow(REQUIRED_COLUMNS)
        for row in TEMPLATE_ROWS:
            writer.writerow(['%.4f' % v for v in row])

    print('Wrote template to: %s' % EXP_CSV_PATH)
    print()
    print('IMPORTANT: These are APPROXIMATE values for testing only.')
    print('For publication-quality results, digitize Fig. 5 of the paper using')
    print('WebPlotDigitizer: https://automeris.io/WebPlotDigitizer/')
    print()
    print('Workflow:')
    print('  1. Open the paper PDF and screenshot Fig. 5a and Fig. 5b separately')
    print('  2. Upload to WebPlotDigitizer')
    print('  3. For each curve ([0/90]s, [0/902]s, [0/904]s):')
    print('     a. Select "2D (X-Y) Plot" mode')
    print('     b. Calibrate axes (strain %: 0 to 2.5; stress MPa: 0 to 40)')
    print('     c. Click "Add Curve" and trace points along the experimental line')
    print('     d. Export as CSV')
    print('  4. Combine the 6 curves (3 stress + 3 stiffness) into one CSV file')
    print('     matching the column order above')
    print('  5. Replace %s with the combined CSV' % EXP_CSV_PATH)


def check_format():
    """Validate that experimental_fig5.csv exists and has correct columns."""
    if not os.path.exists(EXP_CSV_PATH):
        print('ERROR: %s not found' % EXP_CSV_PATH)
        print('Run: python3 scripts/digitize_experimental.py --template')
        return False

    with open(EXP_CSV_PATH) as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            print('ERROR: CSV has no header row')
            return False

        missing = set(REQUIRED_COLUMNS) - set(reader.fieldnames)
        if missing:
            print('ERROR: missing columns: %s' % ', '.join(sorted(missing)))
            print('Required columns: %s' % ', '.join(REQUIRED_COLUMNS))
            return False

        rows = list(reader)
        print('OK: %d rows loaded from %s' % (len(rows), EXP_CSV_PATH))
        print('Columns: %s' % ', '.join(reader.fieldnames))

        # Sanity-check ranges
        for col in REQUIRED_COLUMNS[1:]:
            values = [float(r[col]) for r in rows if r[col]]
            if not values:
                continue
            print('  %s: min=%.3f, max=%.3f' % (col, min(values), max(values)))

    return True


def main():
    parser = argparse.ArgumentParser(
        description='Helper for digitizing experimental data from paper Fig. 5.')
    parser.add_argument('--template', action='store_true',
                        help='Write a template CSV with approximate digitized values')
    parser.add_argument('--check', action='store_true',
                        help='Validate the format of data/experimental_fig5.csv')
    args = parser.parse_args()

    if args.template:
        write_template()
    elif args.check:
        ok = check_format()
        sys.exit(0 if ok else 1)
    else:
        print('Run with --template or --check. See --help for details.')
        print()
        print('Workflow overview:')
        print('  1. Use WebPlotDigitizer to extract points from paper Fig. 5')
        print('  2. Run: python3 scripts/digitize_experimental.py --template')
        print('  3. Edit data/experimental_fig5.csv with your digitized values')
        print('  4. Run: python3 scripts/digitize_experimental.py --check')
        print('  5. Run: python3 scripts/plot_figures.py  (will overlay exp data)')


if __name__ == '__main__':
    main()
