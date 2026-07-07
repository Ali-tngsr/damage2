# MANUAL COHESIVE INSERTION WORKFLOW

This document provides **step-by-step instructions** for inserting cohesive
elements between continuum elements in Abaqus/CAE. This is the only step in
the entire replication pipeline that cannot be fully automated — it must be
done manually in the Abaqus/CAE graphical interface.

**Estimated time:** 15-20 minutes per job × 8 jobs = ~2-3 hours total.

---

## 0. Why This Step Is Manual

The paper uses zero-thickness cohesive elements (COH2D4) inserted between
orthotropic continuum elements (CPS4R) as potential crack paths. In Abaqus,
there are three ways to insert such elements:

| Method | Automation | Why we use / don't use it |
|--------|------------|---------------------------|
| **A) GUI Plugin "Insert Cohesive"** | Manual | ✅ RECOMMENDED — reliable, well-tested |
| **B) Orphan mesh + manual element creation** | Scriptable | ❌ Brittle — complex node-pair matching, fails on irregular meshes |
| **C) Surface-based cohesive (COH2D)** | Scriptable | ❌ Different physics — doesn't match paper methodology |

This workflow uses Method A. The automation scripts (run_pipeline.py etc.)
build everything *except* the cohesive elements, save the .cae, and exit.
You then open the .cae in CAE, run the plugin, save, and re-run the pipeline
with `--resume-from` to apply BCs and submit.

---

## 1. Prerequisites

Before starting, ensure:

- [ ] Abaqus/CAE 2018+ is installed (older versions may lack the cohesive plugin)
- [ ] The "Insert Cohesive Layers" plugin is available. Check by:
  - Opening Abaqus/CAE
  - Menu: **Plug-ins → Abaqus → Cohesive...**
  - If missing, install the SIMULIA "Composite Cohesive Plugin" from the
    SIMULIA user community portal, or use the alternative Method A2 below.

- [ ] `run_pipeline.py` has been run in build mode and produced a `.cae` file
  in `abaqus_jobs/`. Example:
  ```bash
  abaqus cae noGUI=scripts/run_pipeline.py -- --t90=0.255 --job-name=val_090s
  # → produces: abaqus_jobs/val_090s.cae
  ```

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

## 3. Method A1: Using the "Insert Cohesive" Plugin (Preferred)

### Step 3.1 — Switch to the Mesh module

Click **Mesh** in the module dropdown (top-left of viewport), or:
Menu: **Module → Mesh**

### Step 3.2 — Verify the part has been meshed

- In the viewport toolbar, select part `Specimen_Orphan` (not `Specimen`)
- You should see a regular grid of CPS4R elements (4-node quads)
- If not meshed: Menu: **Mesh → Part** (this should re-mesh if needed)

### Step 3.3 — Launch the cohesive insertion plugin

Menu: **Plug-ins → Tools → Insert Cohesive Layers...**

> **If the menu item is missing**, install the plugin:
> 1. Download `composite_cohesive_plugin.zip` from SIMULIA user community
> 2. Extract to `<abaqus_install>/cae/plugins/composite_cohesive`
> 3. Restart Abaqus/CAE

The plugin dialog will appear with these fields:

### Step 3.4 — Configure the plugin

| Field | Value to Enter |
|-------|---------------|
| **Part** | `Specimen_Orphan` |
| **Element Set (Faces/Edges)** | `Potential_Crack_Edges` |
| **Cohesive Section** | `Cohesive_Sec` |
| **Element Type** | `COH2D4` (2D 4-node cohesive) |
| **Thickness** | `1.0` (default — uses section-defined thickness) |
| **Node Offset** | `NONE` (zero-thickness cohesive) |

### Step 3.5 — Run the plugin

Click **OK**. The plugin will:

1. Find all element edges in the `Potential_Crack_Edges` set
2. Duplicate the nodes along those edges
3. Create zero-thickness COH2D4 elements between the duplicate node pairs
4. Assign the `Cohesive_Sec` section to the new elements
5. Update the mesh connectivity

**This takes 30-60 seconds** for a model with ~140 crack path columns
(700 cohesive elements). A status bar will appear.

### Step 3.6 — Verify cohesive insertion

After the plugin completes:

1. **Visually check**: in the viewport, you should see thin red lines at
   each potential crack path location (140 vertical lines for `val_090s`)

2. **Element count check**:
   - Menu: **Mesh → Query → Element count**
   - The total element count should now be:
     - Continuum (CPS4R): original count (unchanged)
     - Cohesive (COH2D4): `5 × (n_cols - 1) = 5 × 139 = 695` for val_090s
   - Example: if original was 1400 CPS4R elements, new total is 2095 (1400 + 695)

3. **Set check**:
   - Menu: **Tools → Set → Create**
   - Name it `CRACK_PATHS` (overwrites the existing empty set)
   - Select all COH2D4 elements (use **filter by type** in the select dialog)
   - Click **Done**

### Step 3.7 — Save the modified .cae

Menu: **File → Save** (or Ctrl+S)

The `abaqus_jobs/val_090s.cae` file is now updated with cohesive elements.

---

## 4. Method A2: Manual Cohesive Insertion (No Plugin)

If the plugin is not available, you can do the same operations manually.
This takes longer (~30 min per job) but doesn't require any plugins.

### Step 4.1 — Switch to Mesh module, select Specimen_Orphan

### Step 4.2 — Edit mesh to add cohesive elements

Menu: **Mesh → Edit...**

In the Edit Mesh dialog:

1. Select **Element** from the dropdown
2. Select **Create** as the operation
3. Set **Element type** to `COH2D4` (click the **Element Type...** button to choose)
4. Set **Section** to `Cohesive_Sec`

### Step 4.3 — Manually create cohesive elements

For each potential crack path column (140 of them for `val_090s`):

1. Identify the 4 nodes of two adjacent CPS4R elements sharing a vertical edge
   - Node 1: top-left node of left element
   - Node 2: top-left node of right element (= duplicate of Node 1)
   - Node 3: bottom-left node of right element
   - Node 4: bottom-left node of left element

2. Click the 4 nodes in order (1, 2, 3, 4) to create a COH2D4 element

3. Repeat for each row (5 rows per column) × each column (140 columns)

> ⚠️ **This is tedious.** Use the plugin (Method A1) if at all possible.
> Method A2 is documented here as a fallback only.

### Step 4.4 — Save the .cae

---

## 5. Common Issues & Solutions

### Issue: "Element set 'Potential_Crack_Edges' not found"

**Cause:** `build_mesoscale_model.py` didn't create the set, or you opened
the wrong .cae file.

**Fix:**
1. In CAE, go to **Tree → Parts → Specimen_Orphan → Sets**
2. Check if `Potential_Crack_Edges` exists
3. If not, re-run `run_pipeline.py` in build mode (without `--resume-from`)

### Issue: Plugin reports "No edges found"

**Cause:** The orphan mesh has no edge set, or the set is on the wrong part.

**Fix:**
1. In the plugin dialog, manually select the part `Specimen_Orphan`
2. Re-check the set dropdown — sometimes the plugin filters by the active part

### Issue: "Cohesive section 'Cohesive_Sec' not assignable"

**Cause:** The section was created on `Specimen` (the original part) but
not propagated to `Specimen_Orphan`.

**Fix:**
1. Go to **Property module**
2. Select part `Specimen_Orphan`
3. Menu: **Section → Assign → Section**
4. Choose `Cohesive_Sec` and assign it
5. Save and retry

### Issue: After insertion, model fails consistency check on submit

**Cause:** Node duplication may have broken element connectivity, or
material orientations are missing on the new cohesive elements.

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

---

## 6. Verification Checklist (Before Submit)

After inserting cohesive elements, verify each item before submitting:

- [ ] **Element count**: total = continuum_count + 5 × (n_cols - 1)
  - For val_090s: 1400 + 695 = 2095
  - For val_0904s (4× taller): 5600 + 695 = 6295
- [ ] **Section assignment**: all COH2D4 elements have `Cohesive_Sec`
- [ ] **Material orientation**: still applied to all elements
- [ ] **Set `CRACK_PATHS`** exists and contains all COH2D4 elements
- [ ] **Mesh quality**: Menu: **Mesh → Verify → Element quality**
  - All elements should pass (no red highlighted elements)
- [ ] **Step settings**: nlgeom=ON, maxNumInc=10000
- [ ] **BCs applied**: Fix_Left_X, Fix_Bottom_Y, Pull_Right_X
- [ ] **Save**: Ctrl+S before closing CAE

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

### Phase 2: Insert cohesive elements (manual, ~2 hours)

For each of the 8 .cae files:
1. `abaqus cae database=abaqus_jobs/<name>.cae`
2. Run **Plug-ins → Insert Cohesive Layers** (Section 3 above)
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
| Run cohesive plugin | ~1 min | ~8 min |
| Verify + save | ~2 min | ~16 min |
| Close + reopen next | ~30 sec | ~4 min |
| **Subtotal (manual)** | **~4 min** | **~32 min** |
| Submit job | ~1 hr | ~8 hours (CPU) |
| Post-process | ~2 min | ~16 min |
| Plot all figures | — | ~5 min |
| **Total** | | **~9 hours** |

> **Note:** The 32 minutes of manual cohesive insertion is the only
> non-automated step. All other phases are scripted.

---

## 10. Alternative: Skip Cohesive, Use Surface-Based Cohesive Behavior

If you cannot install the cohesive plugin and Method A2 is too tedious,
you can use **surface-based cohesive behavior** instead. This is a different
physics formulation but produces qualitatively similar results.

To switch:

1. In **Interaction module**, create a surface-to-surface contact
2. Set **Interaction property** to a new property with:
   - Mechanical → Cohesive Behavior
   - Traction separation: Knn = Kss = Ktt = 1e8 MPa/mm
   - Damage initiation: Max stress = Y_T (use 17 MPa as default)
   - Damage evolution: Energy, G_c = 0.2 N/mm
3. Apply to all crack-path edges as master+slave surfaces

> ⚠️ **Warning:** This method does NOT match the paper's methodology
> (which uses element-based cohesive). Use it only as a last resort.

---

## 11. References

- Abaqus Analysis User's Guide, §32.3 (Cohesive Elements)
- Abaqus Analysis User's Guide, §32.4 (Defining the constitutive response of cohesive elements)
- Abaqus/CAE User's Guide, §69 (Mesh module)
- SIMULIA Cohesive Plugin: https://plugins.3ds.com/ (requires SIMULIA user account)

---

*Last updated: July 2026. If you find errors in this workflow, please open
an issue on the GitHub repository.*
