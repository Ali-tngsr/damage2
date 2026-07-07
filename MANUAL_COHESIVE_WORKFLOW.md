# MANUAL COHESIVE INSERTION WORKFLOW

This document provides **step-by-step instructions** for inserting cohesive
elements between continuum elements in Abaqus/CAE. This is the only step in
the replication pipeline that is done interactively in the GUI.

**Estimated time:** 5-10 minutes per job × 8 jobs = ~1 hour total.

---

## 0. Workflow Summary

The pipeline builds the .cae with everything ready for cohesive insertion:
- Geometry partitioned into 0° and 90° plies
- Mesh of CPS4R continuum elements
- **Edge set `Potential_Crack_Edges`** containing all vertical partition edges
  where cohesive elements should be inserted
- **Edge set `Crack_Paths`** (alternative name)
- Cohesive material `Cohesive_Mat` and section `Cohesive_Sec` already defined

You then:
1. Open the .cae in Abaqus/CAE
2. Use Abaqus' built-in **Edit Mesh → Element** tool to create COH2D4 elements
   along the edges in the set
3. Save the .cae
4. Resume the pipeline with `--resume-only --submit`

---

## 1. Prerequisites

Before starting, ensure:

- [ ] Abaqus/CAE is installed (any version 6.13+ works)
- [ ] `run_pipeline.py` (or one of the driver scripts) has been run in build
      mode and produced a `.cae` file in `abaqus_jobs/`. Example:
  ```bash
  abaqus cae noGUI=scripts/run_pipeline.py -- --t90=0.255 --job-name=val_090s
  # → produces: abaqus_jobs/val_090s.cae
  ```

- [ ] Verify the set exists by listing it from Python (optional):
  ```bash
  abaqus python -c "from odbAccess import openOdb; print('ok')"
  ```

> **No plugin required!** This workflow uses only built-in Abaqus/CAE tools.

---

## 2. Open the .cae File in Abaqus/CAE

From a terminal (Linux/macOS) or Abaqus Command Prompt (Windows):

```bash
cd <path-to>/damage2
abaqus cae database=abaqus_jobs/val_090s.cae
```

> **Tip:** If you're on Windows and `abaqus` is not in PATH, use the full
> path: `"C:\SIMULIA\Commands\abaqus.bat" cae database=abaqus_jobs\val_090s.cae`

Abaqus/CAE will open with the model loaded. You should see:

- **Model Database** (left panel) → Model-1
- **Part** module: `Specimen` and `Specimen_Orphan` parts
- **Property** module: many materials (`Mat_0deg_Vf45`, `Mat_90deg_VfXX.X`,
  `Cohesive_Mat`)
- **Mesh** module: continuum elements (CPS4R)

---

## 3. Insert Cohesive Elements Using Built-in Tools

### Step 3.1 — Switch to the Mesh module

Click **Mesh** in the module dropdown (top-left of viewport), or:
Menu: **Module → Mesh**

### Step 3.2 — Select the Specimen_Orphan part

In the viewport toolbar (top of viewport), make sure the part dropdown shows
`Specimen_Orphan` (NOT `Specimen`). This is the orphan mesh part where we
will insert cohesive elements.

> If you only see `Specimen`, that's also OK — the orphan mesh was created
> as a copy of `Specimen` and both contain the same edge set.

### Step 3.3 — Open the Edit Mesh tool

Menu: **Mesh → Edit...**

In the Edit Mesh dialog:

1. **Category:** Element
2. **Operation:** Create

### Step 3.4 — Configure element type and section

Click the **Element Type...** button and set:

| Field | Value |
|-------|-------|
| Element library | Standard |
| Family | Cohesive |
| Dimensionality | 2D |
| Element type | **COH2D4** (4-node bilinear, quadratic is also OK) |

Click **OK** to close the element type dialog.

In the Edit Mesh dialog, also set:

| Field | Value |
|-------|-------|
| Section | `Cohesive_Sec` |

### Step 3.5 — Select the edges where cohesive elements will be inserted

This is the key step. We want to insert cohesive elements on every vertical
partition edge in the 90° ply region. The pipeline has pre-built the set
`Potential_Crack_Edges` (or `Crack_Paths`) for exactly this purpose.

**Option A: Use the pre-built set (recommended)**

1. In the Edit Mesh dialog, click the prompt arrow next to "Select"
2. In the viewport, click the **Sets** toolbar button (or Menu: Tools → Sets)
3. Select `Potential_Crack_Edges` (or `Crack_Paths`)
4. Click **Done**

All vertical partition edges in the 90° ply will be highlighted.

**Option B: Manual selection (if set is missing)**

1. In the toolbar, click the **Filter** dropdown and choose "Edges"
2. Hold Shift and click each vertical edge in the 90° ply region
   - There are approximately `n_cols - 1 = 139` edges for the validation case
   - They are evenly spaced at intervals of `L / n_cols = 0.5 mm`
3. Click **Done** when all edges are selected

### Step 3.6 — Create the cohesive elements

For each selected edge, Abaqus will create a zero-thickness COH2D4 element
automatically. The procedure is:

1. After selecting edges (Step 3.5), Abaqus will prompt you to confirm
2. Click **Yes** (or **Create**) to generate cohesive elements on all edges
3. The status bar will show progress
4. When complete, you should see thin red lines at each crack path location
   (139 vertical lines for `val_090s`)

> **Note:** The exact menu sequence varies slightly between Abaqus versions.
> In Abaqus 2020+, use:
>   **Mesh → Edit → Element → Create → by Edge Selection**
> In older versions, you may need to:
>   **Mesh → Element → Create** (then pick the 4 nodes of each pair)

### Step 3.7 — Verify cohesive insertion

After creating the cohesive elements:

1. **Visually check**: in the viewport, you should see thin red lines at
   each potential crack path location (139 vertical lines for `val_090s`)

2. **Element count check**:
   - Menu: **Mesh → Query → Element count**
   - The total element count should now be:
     - Continuum (CPS4R): original count (unchanged)
     - Cohesive (COH2D4): `5 × (n_cols - 1) = 5 × 139 = 695` for val_090s
   - Example: if original was 1400 CPS4R elements, new total is 2095

3. **Create CRACK_PATHS set** (if not already present):
   - Menu: **Tools → Set → Create**
   - Name: `CRACK_PATHS`
   - Click the filter dropdown and choose "By Element Type"
   - Select all COH2D4 elements
   - Click **Done**

### Step 3.8 — Save the modified .cae

Menu: **File → Save** (or Ctrl+S)

The `abaqus_jobs/val_090s.cae` file is now updated with cohesive elements.

---

## 4. Alternative: Quick Plugin Method (if available)

If your Abaqus installation has the **"Insert Cohesive Layers"** plugin
(check: Plug-ins menu → look for it), this is faster:

1. Open .cae in Abaqus/CAE (Step 2)
2. Switch to Mesh module
3. Plug-ins → Insert Cohesive Layers
4. Configure:
   - Part: `Specimen_Orphan`
   - Element Set: `Potential_Crack_Edges`
   - Cohesive Section: `Cohesive_Sec`
   - Element Type: `COH2D4`
5. Click OK
6. Save the .cae

This is functionally identical to Section 3 but automates the edge-by-edge
selection. Use whichever is available.

---

## 5. Verification Checklist (Before Submitting)

After inserting cohesive elements, verify each item:

- [ ] **Element count**: total = continuum_count + 5 × (n_cols - 1)
  - For val_090s: 1400 + 695 = 2095
  - For val_0904s (4× taller): 5600 + 695 = 6295
- [ ] **Section assignment**: all COH2D4 elements have `Cohesive_Sec`
  - Check by: Mesh → Query → Element → click any red line
- [ ] **Set `CRACK_PATHS`** exists and contains all COH2D4 elements
- [ ] **Mesh quality**: Menu: **Mesh → Verify → Element quality**
  - All elements should pass (no red highlighted elements)
- [ ] **Save**: Ctrl+S before closing CAE

---

## 6. Common Issues & Solutions

### Issue: "Set 'Potential_Crack_Edges' not found"

**Cause:** The pipeline didn't create the set, or you opened the wrong .cae.

**Fix:**
1. In CAE, go to **Model Tree → Parts → Specimen_Orphan → Sets**
2. Check if `Potential_Crack_Edges` or `Crack_Paths` exists
3. If not, re-run the pipeline in build mode (without `--resume-from`):
   ```bash
   abaqus cae noGUI=scripts/run_pipeline.py -- --t90=0.255 --job-name=val_090s
   ```

### Issue: "Cohesive section 'Cohesive_Sec' not assignable"

**Cause:** The section was created on `Specimen` but not propagated to
`Specimen_Orphan`.

**Fix:**
1. Go to **Property module**
2. Select part `Specimen_Orphan`
3. Menu: **Section → Assign → Section**
4. Choose `Cohesive_Sec` and assign it
5. Save and retry

### Issue: After insertion, model fails consistency check on submit

**Cause:** Element connectivity may be broken, or material orientations
are missing on the new cohesive elements.

**Fix:**
1. In **Mesh module**: Menu: **Verify → Mesh → Analysis checks**
2. Run **Element type consistency** and **Element connectivity** checks
3. Fix any reported issues
4. In **Property module**: ensure all COH2D4 elements have the cohesive section
5. Re-submit

### Issue: Job runs but no cracks form (SDEG stays at 0)

**Cause:** Cohesive strength `Y_T` is too high, or the cohesive section
wasn't assigned the right material.

**Fix:**
1. In **Property module**, inspect `Cohesive_Mat`:
   - Elastic type: TRACTION, K = 1e8 MPa/mm
   - MaxsDamageInitiation: strength = 17 MPa (or local Y_T)
   - DamageEvolution: ENERGY, G_c = 0.2 N/mm
2. Inspect a few COH2D4 elements:
   - Use **Query → Element → Section assignment**
   - Confirm section = `Cohesive_Sec`
3. If material is wrong: re-assign section via Property module

### Issue: Job diverges at first crack onset (around 0.35% strain)

**Cause:** Snap-back in cohesive softening causes convergence failure.

**Fix:**
1. Reduce time increment: in **Step module**, edit Step-1:
   - Initial increment: 0.001 (instead of 0.005)
   - Minimum increment: 1e-15 (instead of 1e-12)
   - Maximum increments: 50000
2. Enable stabilization: in Step editor → **Other → Stabilization**:
   - Method: DISSIPATED_ENERGY_FRACTION
   - Magnitude: 2e-4
3. Re-submit

### Issue: ODB file is huge (>5 GB)

**Cause:** Field output frequency is too high.

**Fix:**
1. In **Step module**, edit Field Output Requests → F-Output-1
2. Set **Frequency** to 20 (save every 20 increments)
3. Re-submit

### Issue: I accidentally created too many cohesive elements

**Cause:** Edges were selected twice or set included wrong edges.

**Fix:**
1. In Mesh module: **Mesh → Edit → Element → Delete**
2. Filter by element type = COH2D4
3. Select all and delete
4. Re-do the cohesive insertion from Step 3.5

### Issue: Want to start over from scratch

**Fix:** Delete the .cae file and re-run the build:
```bash
rm abaqus_jobs/val_090s.cae
abaqus cae noGUI=scripts/run_pipeline.py -- --t90=0.255 --job-name=val_090s
```

---

## 7. After Manual Insertion — Resume the Pipeline

Once you've saved the modified `.cae`, return to the terminal and resume:

```bash
# Resume a single job
abaqus cae noGUI=scripts/run_pipeline.py -- \
    --resume-from=abaqus_jobs/val_090s.cae \
    --submit --job-name=val_090s \
    --t0=0.250 --t90=0.255

# Resume all validation jobs at once
abaqus cae noGUI=scripts/run_validation_sims.py -- --resume-only --submit

# Resume ply number study
abaqus cae noGUI=scripts/run_ply_number_study.py -- --resume-only --submit

# Resume ply thickness study
abaqus cae noGUI=scripts/run_ply_thickness_study.py -- --resume-only --submit
```

The pipeline will:
1. Open the .cae you just edited
2. Set up assembly, BCs, and job
3. Submit the job
4. Wait for completion

---

## 8. Batch Workflow for All 8 Jobs

To minimize manual effort across all 8 jobs:

### Phase 1: Build all .cae files (one command, ~10 min)

```bash
# Build all validation jobs (no submission)
abaqus cae noGUI=scripts/run_validation_sims.py -- --no-submit
# Build ply number study job
abaqus cae noGUI=scripts/run_ply_number_study.py -- --no-submit
# Build all ply thickness study jobs
abaqus cae noGUI=scripts/run_ply_thickness_study.py -- --no-submit
```

After this, you have 8 .cae files in `abaqus_jobs/`:
- val_090s.cae, val_0902s.cae, val_0904s.cae
- pn_090n0.cae
- pt_t90_020.cae, pt_t90_060.cae, pt_t90_100.cae, pt_t90_140.cae

### Phase 2: Insert cohesive elements (manual, ~1 hour)

For each of the 8 .cae files:
1. `abaqus cae database=abaqus_jobs/<name>.cae`
2. Follow Section 3 above (Mesh → Edit → Element → Create)
3. Save (Ctrl+S)
4. Close CAE

### Phase 3: Resume and submit all jobs (one command)

```bash
# Submit validation jobs
abaqus cae noGUI=scripts/run_validation_sims.py -- --resume-only --submit

# Submit ply number study
abaqus cae noGUI=scripts/run_ply_number_study.py -- --resume-only --submit

# Submit ply thickness study
abaqus cae noGUI=scripts/run_ply_thickness_study.py -- --resume-only --submit
```

### Phase 4: Post-process and plot

```bash
# Post-process each ODB (8 commands)
for job in val_090s val_0902s val_0904s pn_090n0 pt_t90_020 pt_t90_060 pt_t90_100 pt_t90_140; do
    abaqus python scripts/postprocess_odb.py --odb abaqus_jobs/${job}.odb --job-name ${job}
done

# Plot all figures
python3 scripts/plot_figures.py --figures 5,9,10,11
```

---

## 9. Time Budget

| Step | Per Job | All 8 Jobs |
|------|---------|------------|
| Build .cae (Phase 1) | ~1 min | ~10 min |
| Open .cae in CAE | ~30 sec | ~4 min |
| Select edges + create cohesive | ~3 min | ~24 min |
| Verify + save | ~1 min | ~8 min |
| Close + reopen next | ~30 sec | ~4 min |
| **Subtotal (manual cohesive)** | **~5 min** | **~40 min** |
| Submit job | ~1 hr | ~8 hours (CPU) |
| Post-process | ~2 min | ~16 min |
| Plot all figures | — | ~5 min |
| **Total** | | **~9 hours** |

---

*Last updated: July 2026. If you find errors in this workflow, please open
an issue on the GitHub repository.*
