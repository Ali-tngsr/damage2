# ROADMAP — Replicating All Figures & Results of UMCM-2025-1979.R1

This roadmap documents **exactly** which steps are automated by the scripts in `scripts/`
and which steps must be performed manually inside Abaqus/CAE. The split is intentional:
automating the CAE GUI clicks is brittle and adds no scientific value, while automating
model generation, post-processing, and plotting saves the most time.

> **Workflow mode:** This roadmap assumes `COHESIVE_INSERTION_MODE = 'manual'`
> (set in `config.py`). In this mode, the pipeline builds geometry/mesh/sets,
> saves the .cae, and exits — leaving cohesive-element insertion to be done
> interactively in Abaqus/CAE via the "Insert Cohesive Layers" plugin.
> See [`MANUAL_COHESIVE_WORKFLOW.md`](./MANUAL_COHESIVE_WORKFLOW.md) for the
> step-by-step GUI guide.

---

## 0. Source Paper — What We Need to Reproduce

**Paper:** *Unraveling Transverse Crack Multiplication in Thin-Ply Orthotropic Laminates: A Stochastic Finite Element Study* (Rumayshah et al., ITB, 2025)

### Target Figures (11 total)

| Fig. | Description | Data Source | Automation |
|------|-------------|-------------|------------|
| 1 | Methodology flowchart | (already in README) | — manual — |
| 2 | (a) Micrograph segmentation, (b) unit cells at 7 Vf | (Scale-1 output) | — manual — (paper images) |
| 3 | Unit cell deformed under 4 loadings | (Scale-1 output) | — manual — (skipped per README §2.2) |
| 4 | Stochastic mesoscale FE model of [0/90₄]s | (model snapshot) | — manual — (Abaqus/CAE screenshot) |
| **5** | (a) Stress-strain curves + (b) stiffness degradation for [0/90]ₛ, [0/90₂]ₛ, [0/90₄]ₛ vs experiment | **3 validation sims** | **automated** |
| 6 | Crack morphology — various layups at 2.5% strain | (ODB visualization) | — manual — (Abaqus screenshot) |
| 7 | Crack morphology — thin-ply at 2.5% strain | (ODB visualization) | — manual — (Abaqus screenshot) |
| 8 | Sequential crack propagation in [0/90₄]s | (ODB visualization) | — manual — (Abaqus screenshots at multiple frames) |
| **9** | (a) Avg σ_x⁹⁰ vs time + (b) normalized E90/E90° vs strain for [0/90/0], [0/90]ₛ, [0/90₂]ₛ | **3 ply-number sims** | **automated** |
| **10** | (a) Avg σ_x⁹⁰ + (b) normalized stiffness for [0/90/0] with t90 = 20, 60, 100, 140 µm | **4 thickness sims** | **automated** |
| **11** | (a) Normalized crack density — ply number; (b) normalized crack density — ply thickness | (from Figs. 9/10 sims) | **automated** |

### Target Table

| Table | Description | Automation |
|-------|-------------|------------|
| 1 | Homogenized properties at 7 Vf | **already in `data/table1_properties.csv`** |

**Bottom line:** 5 of 11 figures (Figs. 5, 9, 10, 11) and Table 1 are fully reproducible by automation. The remaining 6 are visualization screenshots that must be captured manually inside Abaqus/CAE — these cannot be scripted without significant overhead.

---

## 1. Workflow Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  AUTOMATED (Python scripts, no Abaqus CAE clicks needed)        │
└─────────────────────────────────────────────────────────────────┘
         │
         ├─► Step A: Generate input data
         │   • material_table.py (already exists)
         │   • vf_field.py (already exists)
         │   • extract_unit_cell_curves.py (NEW — extract Gc,Fracture energy data)
         │
         ├─► Step B: Generate Abaqus model (.cae / .inp)
         │   • run_validation_sims.py     → 3 jobs: val_[0/90]s, val_[0/902]s, val_[0/904]s
         │   • run_ply_number_study.py    → 3 jobs: pn_[0/90/0], pn_[0/90]s, pn_[0/902]s
         │   • run_ply_thickness_study.py → 4 jobs: pt_t90_020, pt_t90_060, pt_t90_100, pt_t90_140
         │   (All three drivers wrap run_pipeline.py with appropriate layup params.)
         │
         ├─► Step C: Submit & run jobs
         │   • Each driver script supports --submit flag
         │   • Or: submit one-by-one from Abaqus/CAE Job Manager
         │
         ├─► Step D: Extract results from .odb files
         │   • postprocess_odb.py (already exists, EXTENDED)
         │   • Produces: results/<job_name>_summary.csv
         │     Columns: frame, strain, sigma90_mpa, global_stress_mpa, E90_normalized,
         │              damaged_cohesive_values, crack_count, normalized_crack_density
         │
         └─► Step E: Plot all figures
             • plot_figures.py (NEW — produces all 5 automated figures)
             • Outputs: results/figure_05.png, figure_09.png, figure_10.png, figure_11.png

┌─────────────────────────────────────────────────────────────────┐
│  MANUAL (must be done in Abaqus/CAE GUI)                        │
└─────────────────────────────────────────────────────────────────┘
         │
         ├─► Step M1: Open each .cae / .odb file in Abaqus/CAE
         │
         ├─► Step M2: For Figs. 6, 7, 8 — visualize crack damage
         │   • Plot SDEG or STATUS field on deformed shape
         │   • Filter to 90° ply elements (use PLY90_FACES set)
         │   • Hide 0° plies for Fig. 7 (View > Display Group > Replace)
         │   • Capture screenshot at 2.5% strain (or progressive frames for Fig. 8)
         │
         ├─► Step M3: For Fig. 4 — capture model overview
         │   • Show partitioned mesh with Vf-based color mapping
         │   • Highlight one cohesive column (red)
         │
         └─► Step M4: For Figs. 1, 2, 3 — use paper images directly
             (these are scale-1 / methodology figures, not from your sims)
```

---

## 2. The 7 Abaqus Jobs to Run

| # | Job Name | Layup | t90 (µm) | Total Thickness (mm) | Purpose | Figures |
|---|----------|-------|----------|----------------------|---------|---------|
| 1 | `val_090s` | [0/90]ₛ | 250 | 1.0 | Validation | 5, 6 |
| 2 | `val_0902s` | [0/90₂]ₛ | 250 | 1.5 | Validation | 5, 6 |
| 3 | `val_0904s` | [0/90₄]ₛ | 250 | 2.5 | Validation | 5, 6, 8 |
| 4 | `pn_090n0` | [0/90/0] | 250 | 1.0 | Ply number study | 9, 11a |
| 5 | `pn_090s` | [0/90]ₛ | 250 | 1.0 | Ply number study (= val_090s, can reuse) | 9, 11a |
| 6 | `pn_0902s` | [0/90₂]ₛ | 250 | 1.5 | Ply number study (= val_0902s, can reuse) | 9, 11a |
| 7-10 | `pt_t90_020`, `_060`, `_100`, `_140` | [0/90/0] | 20, 60, 100, 140 | varies | Ply thickness study | 10, 11b |

**Optimization:** Jobs 1=5 and 2=6 produce identical results, so we only need to run **7 unique jobs** (val_090s, val_0902s, val_0904s, pn_090n0, pt_t90_020, pt_t90_060, pt_t90_100, pt_t90_140 — actually 8).

---

## 3. Step-by-Step Execution Plan

The pipeline runs in **four logical phases per job batch**:

```
Phase 1: BUILD    (automated)  → produces .cae with geometry/mesh/sets, no cohesive
Phase 2: MANUAL   (CAE GUI)    → user inserts cohesive elements via plugin
Phase 3: RESUME   (automated)  → applies BCs, submits job, waits for completion
Phase 4: POST     (automated)  → extracts results from .odb → CSV
                                     then plots figures from CSVs
```

### Phase A — Setup (Day 0, ~30 min)

1. Verify Abaqus license: `abaqus licensing ratelimit` or open Abaqus/CAE
2. Verify Python 3 + numpy + matplotlib installed: `python3 -c "import numpy, matplotlib"`
3. Verify "Insert Cohesive Layers" plugin is available in Abaqus/CAE:
   - Open CAE → Plug-ins menu → look for "Insert Cohesive Layers" or "Cohesive..."
   - If missing: see MANUAL_COHESIVE_WORKFLOW.md §1 for installation instructions
4. Clone damage2 dev branch:
   ```bash
   git clone -b dev https://github.com/Ali-tngsr/damage2.git
   cd damage2
   ```
5. Generate preview data (sanity check):
   ```bash
   python3 scripts/run_all.py
   # → produces data/table1_transcribed.csv + results/vf_field_preview.csv
   ```
6. Digitize experimental data from paper Fig. 5 (one-time setup):
   ```bash
   python3 scripts/digitize_experimental.py --template
   # → edit data/experimental_fig5.csv with WebPlotDigitizer (see script docs)
   ```

---

### Phase B — Validation Sims (Day 1)

**Goal:** produce Figs. 5 + 6 + 8 data.

#### Phase B-1: BUILD (automated, ~10 min)

```bash
abaqus cae noGUI=scripts/run_validation_sims.py -- --no-submit
# → produces 3 .cae files:
#   abaqus_jobs/val_090s.cae
#   abaqus_jobs/val_0902s.cae
#   abaqus_jobs/val_0904s.cae
```

Each .cae contains geometry, partitions, mesh, materials, and edge sets —
but NO cohesive elements yet. The pipeline will print clear instructions
on what to do next.

#### Phase B-2: MANUAL — Insert Cohesive Elements (manual, ~5 min per job)

For each of the 3 .cae files:

1. Open in Abaqus/CAE:
   ```bash
   abaqus cae database=abaqus_jobs/val_090s.cae
   ```

2. Switch to Mesh module

3. Use **Mesh → Edit → Element → Create** to insert COH2D4 elements:
   - Element type: COH2D4
   - Section: `Cohesive_Sec` (already defined by pipeline)
   - Selection: use the pre-built `Potential_Crack_Edges` set (or `Crack_Paths`)
   - Abaqus will create zero-thickness cohesive elements along all selected edges

4. Verify (see MANUAL_COHESIVE_WORKFLOW.md §5):
   - Element count increased by `5 × (n_cols - 1) = 695`
   - Create set `CRACK_PATHS` containing all COH2D4 elements (optional — pipeline
     will auto-detect cohesive elements by type if missing)

5. Save (Ctrl+S) and close CAE

6. Repeat for `val_0902s.cae` and `val_0904s.cae`

> **No plugin required!** This workflow uses only built-in Abaqus/CAE tools.
> If you have the "Insert Cohesive Layers" plugin, you can use it instead —
> see MANUAL_COHESIVE_WORKFLOW.md §4 for the faster plugin method.

> **Detailed GUI screenshots and troubleshooting:**
> see [`MANUAL_COHESIVE_WORKFLOW.md`](./MANUAL_COHESIVE_WORKFLOW.md)

#### Phase B-3: RESUME + SUBMIT (automated, ~3-4 hours CPU)

```bash
abaqus cae noGUI=scripts/run_validation_sims.py -- --resume-only --submit
```

This will:
1. Open each modified .cae
2. Apply BCs and create the job
3. Submit and wait for completion (sequential)
4. Produce 3 .odb files in `abaqus_jobs/`

#### Phase B-4: POST-PROCESS (automated, ~10 min)

```bash
for job in val_090s val_0902s val_0904s; do
    abaqus python scripts/postprocess_odb.py \
        --odb abaqus_jobs/${job}.odb --job-name ${job}
done
# → produces results/<job>_summary.csv for each
```

---

### Phase C — Ply Number Study (Day 2)

**Goal:** produce Figs. 9 + 11a data.

> **Reuse note:** `[0/90]s` and `[0/902]s` results from Phase B are
> reused for Fig. 9. Only `[0/90/0]` needs to be built fresh.

#### Phase C-1: BUILD

```bash
abaqus cae noGUI=scripts/run_ply_number_study.py -- --no-submit
# → produces 1 new .cae: abaqus_jobs/pn_090n0.cae
```

#### Phase C-2: MANUAL — Insert Cohesive Elements

Same workflow as Phase B-2, but for `pn_090n0.cae` only (~15 min).

#### Phase C-3: RESUME + SUBMIT

```bash
abaqus cae noGUI=scripts/run_ply_number_study.py -- --resume-only --submit
```

#### Phase C-4: POST-PROCESS

```bash
# New job
abaqus python scripts/postprocess_odb.py \
    --odb abaqus_jobs/pn_090n0.odb --job-name pn_090n0

# Reused jobs (already done in Phase B-4 — skip if CSVs exist)
# abaqus python scripts/postprocess_odb.py \
#     --odb abaqus_jobs/val_090s.odb --job-name val_090s
# abaqus python scripts/postprocess_odb.py \
#     --odb abaqus_jobs/val_0902s.odb --job-name val_0902s
```

---

### Phase D — Ply Thickness Study (Day 3)

**Goal:** produce Figs. 10 + 11b data.

#### Phase D-1: BUILD

```bash
abaqus cae noGUI=scripts/run_ply_thickness_study.py -- --no-submit
# → produces 4 new .cae files:
#   abaqus_jobs/pt_t90_020.cae  (t90 = 20 µm)
#   abaqus_jobs/pt_t90_060.cae  (t90 = 60 µm)
#   abaqus_jobs/pt_t90_100.cae  (t90 = 100 µm)
#   abaqus_jobs/pt_t90_140.cae  (t90 = 140 µm)
```

#### Phase D-2: MANUAL — Insert Cohesive Elements

For each of the 4 .cae files, follow MANUAL_COHESIVE_WORKFLOW.md (~1 hour total).

> **Tip:** The 20 µm case has a very thin 90° ply, so the mesh is finer.
> Verify element count carefully — see troubleshooting guide §5 of the workflow.

#### Phase D-3: RESUME + SUBMIT

```bash
abaqus cae noGUI=scripts/run_ply_thickness_study.py -- --resume-only --submit
```

#### Phase D-4: POST-PROCESS

```bash
for job in pt_t90_020 pt_t90_060 pt_t90_100 pt_t90_140; do
    abaqus python scripts/postprocess_odb.py \
        --odb abaqus_jobs/${job}.odb --job-name ${job}
done
```

---

### Phase E — Plot All Figures (Day 3-4, ~5 min)

```bash
python3 scripts/plot_figures.py --figures 5,9,10,11
# → produces 4 PNG files in results/:
#   figure_05.png  (stress-strain + stiffness degradation — validation)
#   figure_09.png  (ply number study: σ90 + E90 norm)
#   figure_10.png  (ply thickness study: σ90 + E90 norm)
#   figure_11.png  (crack density — both studies)
```

---

### Phase F — Manual Screenshots for Visualization Figures (Day 4, ~1 hour)

Open `abaqus_jobs/val_0904s.odb` (and others) in Abaqus/CAE and capture:

1. **Fig. 4** — Model overview (mesh + Vf coloring + one red cohesive column)
2. **Fig. 6** — 4-panel damage morphology at 2.5% strain for [0/90]s, [0/902]s, [0/904]s, [0/90/0]
3. **Fig. 7** — 4-panel thin-ply damage morphology (only 90° plies shown)
4. **Fig. 8** — Sequential frames of [0/904]s as strain increases (typically 6-8 sub-panels)

For each:
- Plot `SDEG` field on deformed shape (scale factor ~5×)
- Use `View > Display Group > Replace` to show only 90° ply elements (PLY90_FACES set)
- For Fig. 7, hide 0° plies entirely
- Save screenshot as PNG at 300 DPI: `File > Print > PNG > 300 DPI`

### Phase G — Compile Final Report (~30 min)

Assemble all PNGs into a single PDF or DOCX with captions matching the paper.

---

## 4. Manual vs Automated — Why This Split

| Aspect | Why Manual | Why Automated |
|--------|------------|---------------|
| Model construction (geometry, mesh, materials) | — | ✅ One script generates all 8 jobs |
| Job submission | ✅ Some labs require queue management | ✅ `--submit` flag handles standard case |
| **Cohesive element insertion** | ✅ Plugin requires GUI; orphan-mesh scripting is brittle | — (auto mode is a future enhancement) |
| ODB visualization (SDEG, STATUS, morphology) | ✅ GUI screenshots are non-trivial to script; Abaqus `session.printOptions` is fragile | — |
| Result extraction (stress, strain, crack count) | — | ✅ Pure I/O, deterministic |
| Plotting (matplotlib) | — | ✅ Reproducible, easy to tweak |
| Experimental data overlay | ✅ Must digitize Fig. 5 from paper using WebPlotDigitizer once | — |

---

## 5. Prerequisites & Calibration Parameters

The following parameters are **NOT explicitly stated** in the paper and must be calibrated:

| Parameter | Recommended Starting Value | Source |
|-----------|---------------------------|--------|
| `rho_sat` (crack saturation density) | 8.0 cracks/mm | Hu et al. [17], calibrate to Fig. 11a |
| `G_c,MT` (fracture energy) | 0.2 N/mm | From unit cell σ-ε curve area × l_char |
| Vf range per thickness row (5 cells) | Interface: U[0,30]%, Transition: U[20,55]%, Center: U[45,75]% | Calibrate to Fig. 2a statistics |
| Mesh element size | 0.125 mm | Run mesh sensitivity study |
| Number of Monte Carlo seeds | ≥ 3 | For statistical stability of stochastic results |
| Applied strain max | 2.5% | Fixed by paper |
| Number of increments | 200-500 (auto-managed by Abaqus) | Static step with nlgeom=ON |

---

## 6. Validation Checkpoints

After running Phase B (validation sims), verify:

- [ ] First crack appears near **0.35% strain** (paper §3.1)
- [ ] [0/90]ₛ matches experimental initial modulus (perfect fit expected)
- [ ] [0/90₂]ₛ and [0/90₄]ₛ slightly overestimate initial modulus (paper §3.1 — documented)
- [ ] Stiffness degradation curve shape matches Fig. 5b qualitatively
- [ ] Peak stress values are in the range of 10-20 MPa (paper Fig. 5a)

After Phase C (ply number study):

- [ ] [0/90/0] retains ~60% stiffness at 2.5% strain (paper §3.3)
- [ ] [0/90₂]ₛ retains ~30% stiffness at 2.5% strain (paper §3.3)

After Phase D (ply thickness study):

- [ ] 20 µm case shows delayed stiffness degradation (paper §3.3)
- [ ] 100 µm and 140 µm cases show non-monotonic peak stress (paper §3.3)

---

## 7. Troubleshooting Guide

| Issue | Likely Cause | Fix |
|-------|-------------|-----|
| Job fails to converge in cracking region | Snap-back in cohesive softening | Reduce `initialInc` to 0.001, enable stabilization |
| No cracks form | Y_T too high | Verify `material_table.interpolate_properties(vf)` returns expected YT values |
| All cohesive elements fail at same strain | vf_field is uniform | Verify `vf_field.py` produces non-uniform field (run `python3 scripts/run_all.py` and inspect histogram) |
| Memory error | Model too fine for [0/90₄]ₛ | Use element size 0.25 mm instead of 0.125 mm |
| `rho_sat` unknown | Referenced to Hu et al. [17] | Start at 7 cracks/mm, calibrate to match Fig. 11a saturation plateau |
| ODB file too large (>5 GB) | Too many field outputs | Reduce frame frequency: `F-Output-1` intervals = 20 instead of 200 |

---

## 8. Time Budget Summary

| Phase | Wall-Clock Time | CPU-Hours | Manual? |
|-------|-----------------|-----------|---------|
| Phase A — Setup | 30 min | 0.5 | ✅ (one-time) |
| Phase B-1: BUILD validation (3 .cae) | 10 min | — | ❌ |
| **Phase B-2: MANUAL cohesive insertion** | **~15 min** | **—** | **✅** |
| Phase B-3: RESUME + SUBMIT (3 jobs) | 3-4 hours | 12-16 | ❌ |
| Phase B-4: POST-PROCESS | 10 min | — | ❌ |
| Phase C-1: BUILD ply-number (1 .cae) | 5 min | — | ❌ |
| **Phase C-2: MANUAL cohesive insertion** | **~5 min** | **—** | **✅** |
| Phase C-3: RESUME + SUBMIT (1 job) | 1-2 hours | 4-8 | ❌ |
| Phase C-4: POST-PROCESS | 5 min | — | ❌ |
| Phase D-1: BUILD thickness (4 .cae) | 15 min | — | ❌ |
| **Phase D-2: MANUAL cohesive insertion** | **~20 min** | **—** | **✅** |
| Phase D-3: RESUME + SUBMIT (4 jobs) | 3-4 hours | 12-16 | ❌ |
| Phase D-4: POST-PROCESS | 15 min | — | ❌ |
| Phase E — Plot all figures | 5 min | — | ❌ |
| Phase F — Manual screenshots (Figs. 4, 6, 7, 8) | 1 hour | — | ✅ |
| Phase G — Report compilation | 30 min | — | ✅ |
| **Total manual effort** | **~2 hours** | — | |
| **Total wall-clock** | **~10-13 hours over 4 days** | **~30-40 CPU-hours** | |

---

## 9. Repository File Inventory (After All Scripts Added)

```
damage2/
├── README.md
├── ROADMAP.md                         ← This file
├── MANUAL_COHESIVE_WORKFLOW.md        ← Step-by-step Abaqus/CAE GUI guide
├── .gitignore
├── data/
│   ├── table1_properties.csv
│   ├── table1_transcribed.csv         (sanity-check artifact)
│   └── experimental_fig5.csv          (digitized once via WebPlotDigitizer)
├── scripts/
│   ├── config.py                      (existing + COHESIVE_INSERTION_MODE flag)
│   ├── material_table.py              (existing)
│   ├── material_interp.py             (existing)
│   ├── vf_field.py                    (existing)
│   ├── mesoscale_common.py            (existing)
│   ├── build_mesoscale_model.py       (existing)
│   ├── Cohesive_Mat.py                (existing, has stochastic variant)
│   ├── Cohesive_Mat2.py               (existing)
│   ├── OrphanMesh.py                  (UPDATED — manual mode reporting)
│   ├── boundaryConditions.py          (UPDATED — resume support + field output freq)
│   ├── postprocess_odb.py             (full ODB extraction)
│   ├── plot_results.py                (basic single-job helper)
│   ├── plot_figures.py                (produces Figs. 5, 9, 10, 11)
│   ├── run_pipeline.py                (UPDATED — --resume-from + manual mode)
│   ├── run_validation_sims.py         (UPDATED — --resume-only flag)
│   ├── run_ply_number_study.py        (UPDATED — --resume-only flag)
│   ├── run_ply_thickness_study.py     (UPDATED — --resume-only flag)
│   ├── run_all.py                     (utility preview)
│   └── digitize_experimental.py       (WebPlotDigitizer helper)
├── abaqus_jobs/                       (gitignored — .cae/.odb/.inp land here)
└── results/                           (gitignored — CSV/PNG land here)
```

### Workflow State Machine

```
                    ┌─────────────────┐
                    │  Phase A: Setup │
                    │  (one-time)     │
                    └────────┬────────┘
                             │
                             ▼
              ┌──────────────────────────┐
              │  Phase B/C/D-1: BUILD    │ ← automated
              │  abaqus cae noGUI=...    │
              │  → produces .cae (no coh)│
              └────────┬─────────────────┘
                       │
                       ▼
              ┌──────────────────────────┐
              │  Phase B/C/D-2: MANUAL   │ ← user opens CAE
              │  Insert cohesive elems   │   uses plugin
              │  Save .cae               │
              └────────┬─────────────────┘
                       │
                       ▼
              ┌──────────────────────────┐
              │  Phase B/C/D-3: RESUME   │ ← automated
              │  abaqus cae noGUI=...    │
              │    --resume-only         │
              │    --submit              │
              │  → produces .odb         │
              └────────┬─────────────────┘
                       │
                       ▼
              ┌──────────────────────────┐
              │  Phase B/C/D-4: POST     │ ← automated
              │  abaqus python           │
              │    postprocess_odb.py    │
              │  → produces _summary.csv │
              └────────┬─────────────────┘
                       │
                       ▼
              ┌──────────────────────────┐
              │  Phase E: PLOT           │ ← automated
              │  python3 plot_figures.py │
              │  → produces PNG figures  │
              └────────┬─────────────────┘
                       │
                       ▼
              ┌──────────────────────────┐
              │  Phase F: SCREENSHOTS    │ ← manual (CAE GUI)
              │  Open .odb in Abaqus/CAE │
              │  Capture Figs. 4, 6, 7, 8│
              └──────────────────────────┘
```
