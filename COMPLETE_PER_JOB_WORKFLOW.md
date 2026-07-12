# COMPLETE PER-JOB WORKFLOW — Step-by-Step for Each of the 8 Jobs

This document describes the EXACT steps to follow for each job (val_090s,
val_0902s, val_0904s, pn_090n0, pt_t90_020, pt_t90_060, pt_t90_100,
pt_t90_140).

**Total time per job:** ~15-20 minutes manual work + 30-60 min simulation.

---

## STEP 1: BUILD THE MODEL (gui_build.py)

1. Open Abaqus/CAE:
   ```cmd
   abaqus cae
   ```

2. **File → Run Script...** → select `scripts/gui_build.py`

3. In the dialog, type the job name (e.g. `val_090s`) → **OK**

4. Wait until you see `BUILD COMPLETE — Model is in memory`

5. **Ctrl+S** to save the .cae file to `abaqus_jobs/<job_name>.cae`

---

## STEP 2: SWITCH TO SPECIMEN PART

1. Switch to **Mesh module**

2. In the viewport toolbar (top), open the part dropdown and select:
   - ✅ **`Specimen`** (NOT `Specimen_Orphan`)

3. In the selection filter dropdown (top-right of viewport), set to:
   - **`Edges`** (not `Faces` or `Surface`)

---

## STEP 3: INSERT COHESIVE SEAMS

1. Menu: **Mesh → Edit...**

2. In the Edit Mesh dialog:
   - **Category**: select **Mesh**
   - **Method**: select **Insert cohesive seams**

3. Click **Settings...** button:
   - Keep all defaults (Elements, Top face nodes, etc. checked)
   - **OK**

4. In the viewport, the prompt asks to select element edges:
   - Click the **Sets** button in the toolbar (or Tools → Sets)
   - Select **`Potential_Crack_Edges`**
   - Click **Select** — all vertical edges highlight
   - Click **Done** in the prompt area

5. Abaqus creates the cohesive elements. Verify:
   - **Mesh → Query → Element count**: should be ~2800 (was ~2100)
   - **Mesh → Query → Element type**: click a thin red line → should be **COH2D4**

---

## STEP 4: SET ELEMENT TYPE FOR COHESIVE ELEMENTS

1. Menu: **Mesh → Element Type...**

2. In the viewport, select all cohesive elements:
   - Click the **Sets** button
   - Select **`CohesiveSeam-1-Elements`**
   - Click **Select** → **Done**

3. In the Element Type dialog:
   - **Element library**: **Standard** ✅
   - **Geometric order**: Linear
   - **Family**: Cohesive
   - **Dimensionality**: 2D
   - **Element type**: **COH2D4**
   - **OK**

---

## STEP 5: ADD VISCOSITY VIA SECTION CONTROLS

For cohesive elements with TRACTION_SEPARATION response, viscosity CANNOT
be added via Material → Damage Stabilization. It must be added via
Section Controls using the Keyword Editor.

### 5a. Remove any existing Damage Stabilization from material

1. Switch to **Property module**
2. Menu: **Material → Manager**
3. Double-click **`Cohesive_Mat`**
4. Go to: **Mechanical → Damage for Traction Separation Laws → Max Stress Damage**
5. Click **Suboptions** button
6. If "Damage Stabilization Cohesive" exists, select it → **Delete**
7. **OK** → **OK** → **Done**

### 5b. Add Section Controls via Keyword Editor

1. In Model Tree (left), right-click on **Model-1** → **Edit Keywords...**

2. In Keywords Editor, press **Ctrl+F** → search for `*Cohesive Section`

3. Find the line that looks like:
   ```
   *Cohesive Section, Elset=..., Material=Cohesive_Mat, Response=TRACTION SEPARATION, Thickness=ANALYTICAL
   0.001,
   ```

4. **Right after** the `0.001,` line, add these two lines:
   ```
   *Section Controls, Name=Coh_Sec_Controls
   1e-4,
   ```

5. The result should look like:
   ```
   *Cohesive Section, Elset=..., Material=Cohesive_Mat, Response=TRACTION SEPARATION, Thickness=ANALYTICAL
   0.001,
   *Section Controls, Name=Coh_Sec_Controls
   1e-4,
   ```

6. **OK** to close Keywords Editor

> **Note:** If you can't find Section Controls button in the GUI, the
> Keyword Editor method above always works across all Abaqus versions.

---

## STEP 6: SET SECTION THICKNESS (ANALYTICAL)

1. Still in **Property module**
2. Menu: **Section → Manager**
3. Double-click **`Cohesive_Sec`**
4. In Edit Section dialog:
   - **Initial thickness**: select **Value**
   - **Value**: `0.001`
5. **OK** → **Done**

> If `Cohesive_Sec` doesn't exist, create it:
> 1. Section → Create
> 2. Name: `Cohesive_Sec`
> 3. Category: Other → Type: Cohesive
> 4. Material: `Cohesive_Mat`
> 5. Response: Traction Separation
> 6. Initial thickness: Value = 0.001
> 7. OK

---

## STEP 7: ASSIGN SECTION TO COHESIVE ELEMENTS

1. Still in **Property module**
2. Menu: **Assign → Section** (or click the Assign Section icon)
3. In viewport, select all cohesive elements:
   - Click **Sets** button
   - Select **`CohesiveSeam-1-Elements`**
   - Click **Select** → **Done**
4. In the dialog, select **`Cohesive_Sec`** → **OK**

---

## STEP 8: SAVE AND FINISH

1. **Ctrl+S** to save the .cae

2. **File → Run Script...** → select `scripts/gui_finish.py`

3. In the dialog, type the same job name (e.g. `val_090s`) → **OK**

4. Wait until you see `FINISH COMPLETE — Ready to Submit`

5. **Ctrl+S** again to save the BCs and Job

---

## STEP 9: SUBMIT THE JOB

1. Switch to **Job module**

2. Menu: **Job → Manager** (or click Job Manager icon)

3. Select your job (e.g. `val_090s`)

4. Click **Submit**

5. Status will change: Submitted → Running → Completed

6. If status shows **Aborted** or **Failed**:
   - Click **Monitor** to see what went wrong
   - Check `abaqus_jobs/<job_name>.msg` and `.dat` for errors
   - Common issues:
     - "Too many attempts" → increase viscosity to 1e-3
     - "Zero thickness" → recheck Step 6
     - Convergence → reduce initialInc to 0.001 in Step module

7. When status is **Completed**, the .odb is ready at:
   ```
   abaqus_jobs/<job_name>.odb
   ```

---

## STEP 10: POST-PROCESS (after all 8 jobs are done)

For each completed job, extract results to CSV:

```cmd
abaqus python scripts/postprocess_odb.py --odb abaqus_jobs/val_090s.odb --job-name val_090s
abaqus python scripts/postprocess_odb.py --odb abaqus_jobs/val_0902s.odb --job-name val_0902s
abaqus python scripts/postprocess_odb.py --odb abaqus_jobs/val_0904s.odb --job-name val_0904s
abaqus python scripts/postprocess_odb.py --odb abaqus_jobs/pn_090n0.odb --job-name pn_090n0
abaqus python scripts/postprocess_odb.py --odb abaqus_jobs/pt_t90_020.odb --job-name pt_t90_020
abaqus python scripts/postprocess_odb.py --odb abaqus_jobs/pt_t90_060.odb --job-name pt_t90_060
abaqus python scripts/postprocess_odb.py --odb abaqus_jobs/pt_t90_100.odb --job-name pt_t90_100
abaqus python scripts/postprocess_odb.py --odb abaqus_jobs/pt_t90_140.odb --job-name pt_t90_140
```

This produces 8 CSV files in `results/`:
- `val_090s_summary.csv`, `val_0902s_summary.csv`, ...
- Each contains per-frame: strain, sigma90, E90_normalized, crack_count, etc.

---

## STEP 11: PLOT ALL FIGURES

After all 8 CSVs are generated:

```cmd
python3 scripts/plot_figures.py --figures 5,9,10,11
```

This produces 4 PNG figures in `results/`:
- `figure_05.png` — stress-strain + stiffness degradation (validation)
- `figure_09.png` — ply number study
- `figure_10.png` — ply thickness study
- `figure_11.png` — crack density (both studies)

---

## QUICK CHECKLIST PER JOB

For each of the 8 jobs, verify:

- [ ] gui_build.py ran successfully, .cae saved
- [ ] Switched to Specimen part (not Specimen_Orphan)
- [ ] Selection filter set to Edges
- [ ] Insert cohesive seams: used Potential_Crack_Edges set
- [ ] Element count increased (~2800 vs ~2100)
- [ ] Element type COH2D4 assigned to cohesive elements
- [ ] Damage Stabilization removed from material (if was added)
- [ ] Section Controls added via Keyword Editor (viscosity=1e-4)
- [ ] Cohesive_Sec section thickness = 0.001 (ANALYTICAL)
- [ ] Cohesive_Sec assigned to CohesiveSeam-1-Elements
- [ ] gui_finish.py ran successfully
- [ ] Job submitted → Completed (not Aborted)
- [ ] .odb file exists

After all 8 jobs:
- [ ] postprocess_odb.py run on all 8 .odb files
- [ ] 8 CSV files in results/
- [ ] plot_figures.py produces 4 PNGs

---

## TIME BUDGET PER JOB

| Step | Time |
|------|------|
| 1. Build (gui_build.py) | 2 min |
| 2-3. Insert cohesive seams | 5 min |
| 4. Set element type | 2 min |
| 5. Add viscosity (keyword editor) | 3 min |
| 6-7. Section thickness + assign | 3 min |
| 8. Save + finish (gui_finish.py) | 1 min |
| 9. Submit + wait for completion | 30-60 min |
| **Total manual per job** | **~16 min** |
| **Total for 8 jobs** | **~2-3 hours manual** |
| **Total simulation time** | **~4-8 hours CPU** |

---

## TROUBLESHOOTING QUICK REFERENCE

| Error | Fix |
|-------|-----|
| Zero thickness error | Step 6: set thickness=0.001 |
| Too many attempts | Step 5: increase viscosity to 1e-3 |
| Cannot use *DAMAGE STABILIZATION | Step 5a: remove from material, use Section Controls |
| No SDEG in ODB | Step 4: verify COH2D4 element type |
| No cracks (SDEG=0) | Step 5: verify viscosity is set, check material strength |
| Job Aborted | Check .msg file, increase viscosity or reduce increment size |
