# -*- coding: utf-8 -*-
"""
Central configuration for the Abaqus replication workflow.

Python 2.7 compatible.

This config is the single source of truth for ALL job parameters across:
  - run_validation_sims.py
  - run_ply_number_study.py
  - run_ply_thickness_study.py
  - postprocess_odb.py
  - plot_figures.py
"""

PROJECT_NAME = "thin_ply_transverse_crack_replication"

# =============================================================================
# Geometry (from paper §2.2 — specimen dimensions)
# =============================================================================
GAUGE_LENGTH_MM = 70.0           # L — gauge length
SPECIMEN_LENGTH_MM = 110.0       # full specimen length
SPECIMEN_WIDTH_MM = 20.0         # out-of-plane width (used for stress = F/A)
MAX_ENGINEERING_STRAIN = 0.025   # 2.5% — paper §2.2

# =============================================================================
# Material / cohesive settings (from paper §2.2)
# =============================================================================
PENALTY_STIFFNESS = 1.0e8        # MPa/mm — uniform across all cohesive elements
DEFAULT_RHO_SAT = 8.0            # cracks/mm — calibrate from Fig. 11a
N_THROUGH_THICKNESS_CELLS = 5    # 90° ply divided into 5 sub-cells through thickness
DEFAULT_FRACTURE_ENERGY = 0.2    # N/mm — G_c,MT estimate, calibrate from stiffness slope

# Ply thickness for validation case (paper §2.2: 255 µm elementary ply)
T90_VALIDATION_MM = 0.255        # = 255 µm
T0_PLY_MM = 0.250                # 0° ply thickness (250 µm, constant in parametric study)

# =============================================================================
# Mesh settings
# =============================================================================
DEFAULT_N_COLS = 140             # along specimen length
DEFAULT_N_ROWS = 5               # through 90° ply thickness
DEFAULT_SEED = 2026              # random seed for stochastic Vf field
DEFAULT_ELEMENT_SIZE = 0.125     # mm — mesoscale mesh element size

# =============================================================================
# Vf distribution rules (paper §2.2 — spatial Vf assignment)
# =============================================================================
VF_RANGES = {
    'interface': (0.0, 30.0),    # rows 0, 4 — resin-rich near 0°/90° boundary
    'transition': (20.0, 55.0),  # rows 1, 3
    'centerline': (45.0, 75.0),  # row 2 — fiber-rich core
}

# =============================================================================
# JOB REGISTRY — all 8 jobs needed to reproduce the paper's figures
# =============================================================================
# Each job specifies:
#   name       : unique job name (also used as .odb filename)
#   layup      : human-readable layup notation
#   stack      : list of "0" / "90" entries (top-to-bottom)
#   t90_mm     : thickness of each 90° ply (mm)
#   t0_mm      : thickness of each 0° ply (mm) — fixed at 250 µm
#   purpose    : which paper figures this job contributes to
#   rho_sat    : crack saturation density (cracks/mm)
#
# Notes:
#   - For multi-ply 90° stacks (e.g. [0/90₂]ₛ), the build_mesoscale_model.py
#     currently treats the whole 90° block as one t90 region. This is a known
#     simplification — to truly model [0/90/90/0], the partitioning logic in
#     build_mesoscale_model.py would need to be extended. For now, the model
#     uses an "equivalent t90" approach: t90_total = n_ply * t90_single.
#   - The [0/90/0] layup is the same as [0/90]ₛ structurally; they differ
#     only in total thickness (1.0 mm vs 0.5 mm if symmetric).

JOBS = [
    # --- Validation sims (Phase B) → Figures 5, 6 ---
    {
        'name': 'val_090s',
        'layup': '[0/90]s',
        'stack': ['0', '90', '0'],
        't90_mm': 0.255,
        't0_mm': T0_PLY_MM,
        'total_thickness_mm': 1.0,
        'purpose': ['fig5', 'fig6', 'fig9', 'fig11a'],
        'rho_sat': DEFAULT_RHO_SAT,
    },
    {
        'name': 'val_0902s',
        'layup': '[0/902]s',
        'stack': ['0', '90', '90', '0'],
        't90_mm': 0.510,            # 2 × 255 µm (treated as single block)
        't0_mm': T0_PLY_MM,
        'total_thickness_mm': 1.5,
        'purpose': ['fig5', 'fig6', 'fig9', 'fig11a'],
        'rho_sat': DEFAULT_RHO_SAT,
    },
    {
        'name': 'val_0904s',
        'layup': '[0/904]s',
        'stack': ['0', '90', '90', '90', '90', '0'],
        't90_mm': 1.020,            # 4 × 255 µm (treated as single block)
        't0_mm': T0_PLY_MM,
        'total_thickness_mm': 2.5,
        'purpose': ['fig5', 'fig6', 'fig8'],
        'rho_sat': DEFAULT_RHO_SAT,
    },

    # --- Ply number study (Phase C) → Figures 9, 11a ---
    # Note: [0/90]s and [0/902]s reuse val_090s and val_0902s jobs
    {
        'name': 'pn_090n0',         # [0/90/0] — single 90° ply, non-symmetric
        'layup': '[0/90/0]',
        'stack': ['0', '90', '0'],
        't90_mm': 0.255,
        't0_mm': T0_PLY_MM,
        'total_thickness_mm': 0.755,  # 2*0.25 + 0.255
        'purpose': ['fig9', 'fig11a'],
        'rho_sat': DEFAULT_RHO_SAT,
    },

    # --- Ply thickness study (Phase D) → Figures 10, 11b ---
    # All [0/90/0] with varying t90
    {
        'name': 'pt_t90_020',
        'layup': '[0/90/0]',
        'stack': ['0', '90', '0'],
        't90_mm': 0.020,            # 20 µm — thin-ply
        't0_mm': T0_PLY_MM,
        'total_thickness_mm': 0.520,
        'purpose': ['fig10', 'fig11b'],
        'rho_sat': DEFAULT_RHO_SAT,
    },
    {
        'name': 'pt_t90_060',
        'layup': '[0/90/0]',
        'stack': ['0', '90', '0'],
        't90_mm': 0.060,            # 60 µm
        't0_mm': T0_PLY_MM,
        'total_thickness_mm': 0.560,
        'purpose': ['fig10', 'fig11b'],
        'rho_sat': DEFAULT_RHO_SAT,
    },
    {
        'name': 'pt_t90_100',
        'layup': '[0/90/0]',
        'stack': ['0', '90', '0'],
        't90_mm': 0.100,            # 100 µm
        't0_mm': T0_PLY_MM,
        'total_thickness_mm': 0.600,
        'purpose': ['fig10', 'fig11b'],
        'rho_sat': DEFAULT_RHO_SAT,
    },
    {
        'name': 'pt_t90_140',
        'layup': '[0/90/0]',
        'stack': ['0', '90', '0'],
        't90_mm': 0.140,            # 140 µm
        't0_mm': T0_PLY_MM,
        'total_thickness_mm': 0.640,
        'purpose': ['fig10', 'fig11b'],
        'rho_sat': DEFAULT_RHO_SAT,
    },
]


def get_job_by_name(name):
    """Return the job dict matching `name`, or None."""
    for job in JOBS:
        if job['name'] == name:
            return job
    return None


def get_jobs_by_purpose(purpose_tag):
    """Return list of jobs whose 'purpose' contains purpose_tag (e.g. 'fig5')."""
    return [j for j in JOBS if purpose_tag in j.get('purpose', [])]


def list_jobs():
    """Pretty-print all jobs for sanity checking."""
    print('%-15s %-12s %8s %8s %8s  %s' % (
        'Name', 'Layup', 't90_mm', 't0_mm', 'total', 'Purposes'))
    print('-' * 80)
    for j in JOBS:
        print('%-15s %-12s %8.3f %8.3f %8.3f  %s' % (
            j['name'], j['layup'], j['t90_mm'], j['t0_mm'],
            j['total_thickness_mm'], ','.join(j['purpose'])))


# =============================================================================
# Sanity-check invoked when running this file directly
# =============================================================================
if __name__ == '__main__':
    list_jobs()
    print()
    print('Total jobs: %d' % len(JOBS))
    print('Validation jobs (fig5): %d' % len(get_jobs_by_purpose('fig5')))
    print('Ply-number study jobs (fig9): %d' % len(get_jobs_by_purpose('fig9')))
    print('Ply-thickness study jobs (fig10): %d' % len(get_jobs_by_purpose('fig10')))
