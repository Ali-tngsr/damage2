# Workflow — GUI Pipeline

This document describes the **manual cohesive insertion** workflow used to reproduce the paper's figures. All Abaqus scripts are Python 2.7 compatible.

## Pipeline Stages

```
[Stage 0]  Sanity check
    └── run_all.py  →  data/table1_transcribed.csv + results/vf_field_preview.csv

[Stage 1]  Build (automated, GUI or CLI)
    └── gui_build.py  →  abaqus_jobs/<job>.cae  (geometry + mesh + edge sets)

[Stage 2]  Manual cohesive insertion (CAE GUI)
    └── Mesh → Edit → Insert cohesive seams  →  CohesiveSeam-1-Elements

[Stage 3]  Resume (automated, GUI or CLI)
    └── gui_finish.py  →  BCs + step + job created, ready to submit

[Stage 4]  Submit
    └── Job Manager → Submit  (or `abaqus job=<name> cpus=4 interactive`)

[Stage 5]  Post-process
    └── postprocess_odb.py  →  results/<job>_summary.csv

[Stage 6]  Plot figures
    └── plot_figures.py  →  results/figure_*.png
```

## Stage 0 — One-time setup

```bash
python scripts/run_all.py
python scripts/digitize_experimental.py --template
```

- `run_all.py` re-emits `data/table1_transcribed.csv` and a `results/vf_field_preview.csv` for sanity check.
- `digitize_experimental.py --template` writes the placeholder experimental CSV. Replace its values with actual digitized data from the paper's Fig. 5 using WebPlotDigitizer.

## Stage 1 — Build

### Option A: GUI (recommended for single jobs)

```
abaqus cae
File → Run Script... → scripts/gui_build.py
```

`gui_build.py` calls `run_pipeline.run_pipeline(submit_job=False)`. It will:
1. Build geometry (rectangle, 2D planar)
2. Apply horizontal + vertical partitions
3. Assign stochastic Vf-based orthotropic materials
4. Mesh the continuum part (CPS4R)
5. Create `Potential_Crack_Edges` set
6. Save the `.cae` and stop

### Option B: Command line (batch)

```bash
abaqus cae noGUI=scripts/run_validation_sims.py -- --no-submit
abaqus cae noGUI=scripts/run_ply_number_study.py -- --no-submit
abaqus cae noGUI=scripts/run_ply_thickness_study.py -- --no-submit
```

## Stage 2 — Manual cohesive insertion

Open the saved `.cae` in CAE and follow these steps:

1. **Mesh module** → `Mesh → Edit...`
2. **Category:** Mesh  →  **Method:** Insert cohesive seams
3. Select the geometric part (e.g. `Specimen`, **not** `Specimen_Orphan`)
4. Click **Sets...** → select `Potential_Crack_Edges` → Done
5. Verify the new `CohesiveSeam-1-Elements` set has the expected element count
6. **Property module** → assign `Cohesive_Sec` to `CohesiveSeam-1-Elements`
7. **Keyword Editor** (Model → Edit Keywords): add `*Section Controls` with viscosity `1e-4` after the `*Cohesive Section` block
8. Save (`Ctrl+S`)

## Stage 3 — Resume

```
File → Run Script... → scripts/gui_finish.py
```

`gui_finish.py` calls `boundaryConditions.setup_assembly_and_run(skip_if_exists=True)`. It will:
1. Detect the manually-inserted `CohesiveSeam-1-Elements`
2. Force element type to `COH2D4` and assign `Cohesive_Sec`
3. Create assembly instance, static step, BCs, and the job
4. Save the `.cae` again

## Stage 4 — Submit

- **GUI:** Job Manager → select job → Submit
- **CLI:** `abaqus job=<job_name> cpus=4 interactive`

## Stage 5 — Post-process

```bash
abaqus python scripts/postprocess_odb.py --odb abaqus_jobs/val_090s.odb --job-name val_090s
```

Output: `results/val_090s_summary.csv` with columns `strain_pct, sigma90_volumetric_mpa, global_stress_mpa, E90_normalized, crack_count, normalized_crack_density`.

## Stage 6 — Plot figures

```bash
python scripts/plot_figures.py --figures 5,9,10,11
```

Output PNGs land in `results/figure_05_*.png`, `figure_09_*.png`, etc.

## Job registry (8 jobs)

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

All job parameters (geometry, layup, rho_sat, t90, t0) are defined in `scripts/config.py` — single source of truth.

## Time budget

| Phase | Time |
|-------|------|
| Build (per job) | ~5 min |
| Manual cohesive insertion (per job) | ~15 min |
| Submit (per job, 4 CPUs) | 30–90 min |
| Post-process + plot | ~5 min per job |
| **Total (8 jobs)** | **~10–13 hours** |

## Troubleshooting

- **`Lost connection to driverLM`** → License server dropped. Disable sleep, restart FLEXlm service.
- **`Too many attempts`** → Convergence issue. Increase viscosity (Section Controls) to `1e-3`.
- **`Zero stiffness element`** → Cohesive section missing `Initial thickness: Specify → 0.001`.
- **`CohesiveSeam-1-Elements not found`** → You forgot Stage 2 (manual insertion in CAE).
