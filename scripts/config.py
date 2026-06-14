# -*- coding: utf-8 -*-
"""
Central configuration for the Abaqus replication workflow.

Python 2.7 compatible.
"""

PROJECT_NAME = "thin_ply_transverse_crack_replication"

# Geometry values taken from the paper and the provided replication plan.
GAUGE_LENGTH_MM = 70.0
SPECIMEN_LENGTH_MM = 110.0
SPECIMEN_WIDTH_MM = 20.0
MAX_ENGINEERING_STRAIN = 0.025

# Validation layups from the paper.
LAYUPS = {
    "SINGLE_90": {
        "stack": ["0", "90", "0"],
        "t90_mm": 0.255,
        "total_thickness_mm": 1.0,
    },
    "DOUBLE_90": {
        "stack": ["0", "90", "90", "0"],
        "t90_mm": 0.255,
        "total_thickness_mm": 1.5,
    },
    "QUAD_90": {
        "stack": ["0", "90", "90", "90", "90", "0"],
        "t90_mm": 0.255,
        "total_thickness_mm": 2.5,
    },
}

# Cohesive settings from the paper/plan.
PENALTY_STIFFNESS = 1.0e8  # MPa/mm
DEFAULT_RHO_SAT = 8.0      # cracks/mm, calibrate from crack saturation plot
N_THROUGH_THICKNESS_CELLS = 5

# Mesh settings for the starter model.
DEFAULT_N_COLS = 140
DEFAULT_N_ROWS = 5
DEFAULT_SEED = 2026
