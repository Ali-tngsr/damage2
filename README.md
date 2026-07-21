# Damage2 — Script Workflow Branch

Replication & extension of:
**Rumayshah et al. (ITB)** — *Unraveling Transverse Crack Multiplication in Thin-Ply Orthotropic Laminates: A Stochastic Finite Element Study* — Mechanics of Advanced Materials and Structures (UMCM-2025-1979.R1).

This branch implements the **single-script workflow**: one consolidated script `abaqus_laminate_partitioning.py` handles geometry + partitioning + materials + mesh + assembly + BCs + job, in two run modes (`build` and `resume`).

---

## Repository Layout

```
.
├── README.md                            (this file)
├── WORKFLOW.md                          (step-by-step pipeline)
├── data/
│   ├── table1_properties.csv            (homogenized GF/PP props at 7 Vf levels)
│   ├── table1_transcribed.csv
│   └── experimental_fig5.csv            (digitized experimental data for Fig. 5)
└── scripts/
    ├── abaqus_laminate_partitioning.py  (consolidated build+resume script)
    ├── postprocess_odb.py               (extract stress-strain, E90, crack density)
    └── plot_figures.py                  (Figs. 5, 9, 10, 11 — robust to missing data)
```

## Design philosophy

Unlike the GUI branch (which splits the pipeline across many small scripts and requires `gui_build.py` + manual CAE work + `gui_finish.py`), this branch packs everything into a single file:

- **`JOB_PROFILES`** dict — 8 pre-defined jobs matching `config.py` from the GUI branch
- **`SCALE_FACTOR`** — scale specimen length to fit available compute
- **`APPLY_AUTO_MESH_SIZE`** — auto-set mesh size = `t90/n_cells` (square cells)
- **`CRACK_SELECTION_MODE`** — `RHO_BASED` or `FIXED_SPACING`
- **Two run modes:**
  - `run_mode = 'build'` — geometry + partitions + materials + mesh + save `.cae`
  - `run_mode = 'resume'` — process manual cohesive + assembly + BC + job

The single manual step (inserting cohesive elements in CAE) is unavoidable because Abaqus's `Insert cohesive seams` tool has no stable Python API.

## Quick Start

1. **Build all 8 jobs:**
   ```
   abaqus cae noGUI=scripts/abaqus_laminate_partitioning.py
   ```
   (run 8 times, one per `ACTIVE_JOB`)

2. **Insert cohesive elements manually** for each `.cae` (see `WORKFLOW.md`).

3. **Resume + save:**
   ```
   abaqus cae noGUI=scripts/abaqus_laminate_partitioning.py
   ```
   (set `run_mode = 'resume'`, run 8 times)

4. **Submit:**
   ```
   abaqus job=val_090s cpus=4 interactive
   ```

5. **Post-process + plot:**
   ```
   abaqus python scripts/postprocess_odb.py --odb val_090s.odb
   python scripts/plot_figures.py --figures 5,9,10,11
   ```

See **WORKFLOW.md** for the full step-by-step pipeline.

## Key configuration (top of `abaqus_laminate_partitioning.py`)

```python
SCALE_FACTOR = 0.25           # 1.0 = paper values (L=80mm)
APPLY_AUTO_MESH_SIZE = True   # mesh_element_size = t90/n_cells
CRACK_SELECTION_MODE = 'RHO_BASED'   # or 'FIXED_SPACING'
CRACK_SPACING_MM = 0.5

cohesive_strength = 17.0          # MPa
cohesive_fracture_energy = 0.2    # N/mm
cohesive_viscosity = 1.0e-4       # Section Controls
cohesive_initial_thickness = 0.001  # mm

applied_strain = 0.025            # 2.5%
job_cpus = 4
```

## 8 Job profiles

| Job | Layup | t90 (mm) | n90 | Purpose |
|-----|-------|----------|-----|---------|
| `val_090s`   | [0/90]s   | 0.255 | 1 | Figs 5, 6, 9, 11a |
| `val_0902s`  | [0/902]s  | 0.255 | 2 | Figs 5, 6, 9, 11a |
| `val_0904s`  | [0/904]s  | 0.255 | 4 | Figs 5, 6, 8 |
| `pn_090n0`   | [0/90/0]  | 0.255 | 1 | Figs 9, 11a |
| `pt_t90_020` | [0/90/0]  | 0.020 | 1 | Figs 10, 11b |
| `pt_t90_060` | [0/90/0]  | 0.060 | 1 | Figs 10, 11b |
| `pt_t90_100` | [0/90/0]  | 0.100 | 1 | Figs 10, 11b |
| `pt_t90_140` | [0/90/0]  | 0.140 | 1 | Figs 10, 11b |

To switch jobs, change `ACTIVE_JOB` at the top of the script:
```python
ACTIVE_JOB = 'val_090s'   # or 'pt_t90_020', etc.
```
