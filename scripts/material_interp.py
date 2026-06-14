# -*- coding: utf-8 -*-
"""Table 1 property interpolation helper.

This file intentionally avoids pandas/f-strings so it can run both in modern
Python and in older Abaqus Python interpreters.
"""
from __future__ import print_function

import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from mesoscale_common import default_table_path, get_properties, read_table_csv


def get_properties_from_csv(vf_target, csv_path=None, units='GPa'):
    """Interpolate properties from the project CSV without third-party packages."""
    if csv_path is None:
        csv_path = default_table_path()
    if not os.path.exists(csv_path):
        raise IOError('Could not find property table: %s' % csv_path)

    rows = read_table_csv(csv_path)
    rows.sort(key=lambda item: item['Vf'])
    vf_value = float(vf_target)

    if vf_value <= rows[0]['Vf']:
        lower = upper = rows[0]
    elif vf_value >= rows[-1]['Vf']:
        lower = upper = rows[-1]
    else:
        lower = rows[0]
        upper = rows[-1]
        for idx in range(1, len(rows)):
            if vf_value <= rows[idx]['Vf']:
                lower = rows[idx - 1]
                upper = rows[idx]
                break

    props = {'Vf': max(rows[0]['Vf'], min(vf_value, rows[-1]['Vf']))}
    names = ('E11', 'nu12', 'E22', 'nu23', 'YT', 'G12', 'G23')
    for name in names:
        if lower['Vf'] == upper['Vf']:
            value = lower[name]
        else:
            ratio = (vf_value - lower['Vf']) / (upper['Vf'] - lower['Vf'])
            value = lower[name] + ratio * (upper[name] - lower[name])
        if units == 'MPa' and name in ('E11', 'E22', 'G12', 'G23'):
            value *= 1000.0
        props[name] = float(value)
    return props


if __name__ == '__main__':
    test_vf = 45.0
    print('Testing built-in table for Vf = %s%%:' % test_vf)
    print(get_properties(test_vf, units='GPa'))
    print('Testing CSV table for Vf = %s%%:' % test_vf)
    print(get_properties_from_csv(test_vf))
