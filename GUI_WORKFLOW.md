# GUI WORKFLOW — Fully Graphical Workflow for Abaqus/CAE

This guide shows how to run the entire replication pipeline from within the
Abaqus/CAE graphical interface — **no command line needed** (except for
opening CAE itself and for post-processing at the end).

**Estimated time:** ~10 minutes per job (5 min build + 5 min cohesive + finish).

---

## 0. Overview

```
┌─────────────────────────────────────────────────────────┐
│  STEP 1: Open Abaqus/CAE                                │
│  (command: abaqus cae)                                  │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│  STEP 2: File → Run Script → gui_build.py               │
│  (dialog: enter job name, e.g. "val_090s")              │
│  → Model built in memory, .cae saved                    │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│  STEP 3: Manual Cohesive Insertion                      │
│  (Mesh module → Edit → Element → Create → COH2D4)       │
│  → Use Potential_Crack_Edges set                        │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│  STEP 4: Save .cae (Ctrl+S)                             │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│  STEP 5: File → Run Script → gui_finish.py              │
│  (dialog: enter same job name)                          │
│  → BCs + Job created                                    │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│  STEP 6: Job module → Job Manager → Submit              │
│  → Wait for completion                                  │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│  STEP 7: Post-process (command line, one command)       │
│  abaqus python scripts/postprocess_odb.py --odb ...     │
└─────────────────────────────────────────────────────────┘
```

---

## 1. Open Abaqus/CAE

From a terminal or Abaqus Command Prompt:

```bash
abaqus cae
```

> On Windows, you can also use: Start Menu → Abaqus → Abaqus CAE

Abaqus/CAE will open with an empty `Model-1`.

---

## 2. Build the Model (gui_build.py)

### Step 2.1 — Run the build script

Menu: **File → Run Script...**

Navigate to your `damage2/scripts/` directory and select **`gui_build.py`**.

### Step 2.2 — Select job in dialog

A dialog will appear titled "Build Model" listing all available jobs:

```
Available jobs:
  1. val_090s ([0/90]s, t90=0.255 mm)
  2. val_0902s ([0/902]s, t90=0.510 mm)
  3. val_0904s ([0/904]s, t90=1.020 mm)
  4. pn_090n0 ([0/90/0], t90=0.255 mm)
  5. pt_t90_020 ([0/90/0], t90=0.020 mm)
  6. pt_t90_060 ([0/90/0], t90=0.060 mm)
  7. pt_t90_100 ([0/90/0], t90=0.100 mm)
  8. pt_t90_140 ([0/90/0], t90=0.140 mm)

Enter the job name to build:
```

Type the job name (e.g. `val_090s`) and click **OK**.

### Step 2.3 — Wait for build to complete

The script will:
1. Build geometry (partitions for 0° and 90° plies)
2. Assign stochastic Vf-based materials
3. Create cohesive material and section
4. Mesh the part with CPS4R elements
5. Create edge sets (`Potential_Crack_Edges`, `Crack_Paths`, `Ply90_Faces`)
6. Create orphan mesh copy
7. Save the .cae file to `abaqus_jobs/<job_name>.cae`

You'll see progress in the message area at the bottom of CAE. When complete,
you'll see:

```
BUILD COMPLETE — Model is in memory
...
NEXT STEPS:
  1. Switch to Mesh module
  2. Use Mesh > Edit > Element > Create to insert COH2D4 ...
```

The model is now in memory and visible in the viewport.

---

## 3. Manual Cohesive Insertion

### Step 3.1 — Switch to Mesh module

In the module dropdown (top-left of viewport), select **Mesh**.

### Step 3.2 — Verify you're on the right part

In the viewport toolbar, the part dropdown should show `Specimen_Orphan`
(or `Specimen` — both work).

### Step 3.3 — Open Edit Mesh tool

Menu: **Mesh → Edit...**

In the Edit Mesh dialog:
- **Category:** Element
- **Operation:** Create

### Step 3.4 — Set element type

Click **Element Type...** button and configure:

| Field | Value |
|-------|-------|
| Element library | Standard |
| Family | Cohesive |
| Dimensionality | 2D |
| Element type | **COH2D4** |

Click **OK**.

### Step 3.5 — Set section

In the Edit Mesh dialog, set:
- **Section:** `Cohesive_Sec`

### Step 3.6 — Select edges

Click the selection prompt. Then select all edges in the `Potential_Crack_Edges` set:

**Method A (fastest):** Use the set directly
1. Click the **Sets** button in the toolbar (or Menu: Tools → Sets)
2. Select `Potential_Crack_Edges`
3. Click **Done**

**Method B (manual):** Click each vertical edge in the 90° ply region
(there are ~139 edges for validation jobs).

### Step 3.7 — Create cohesive elements

After selecting edges, click **Create** (or **OK**).
Abaqus will create zero-thickness COH2D4 elements along all selected edges.

You should see thin red lines appear at each crack path location.

### Step 3.8 — Verify

- Menu: **Mesh → Query → Element count**
- Total should be: original_count + 5 × (n_cols - 1)
  - For val_090s: ~1400 + 695 = ~2095

### Step 3.9 — (Optional) Create CRACK_PATHS set

Menu: **Tools → Set → Create**
- Name: `CRACK_PATHS`
- Select all COH2D4 elements (filter by type)
- Click **Done**

> This step is optional — the post-processor can auto-detect cohesive elements.

---

## 4. Save the .cae

Menu: **File → Save** (or **Ctrl+S**)

The `abaqus_jobs/<job_name>.cae` file is now updated with cohesive elements.

---

## 5. Set Up BCs and Job (gui_finish.py)

### Step 5.1 — Run the finish script

Menu: **File → Run Script...**

Select **`gui_finish.py`**.

### Step 5.2 — Enter job name in dialog

A dialog will appear:

```
Enter the job name (must match what you used in gui_build.py).

Valid names: val_090s, val_0902s, val_0904s, pn_090n0,
             pt_t90_020, pt_t90_060, pt_t90_100, pt_t90_140
```

Type the **same** job name you used in Step 2.2 (e.g. `val_090s`) and click **OK**.

### Step 5.3 — Wait for setup

The script will:
1. Create the assembly (instance the part)
2. Apply material orientation
3. Create Static Step with nlgeom=ON
4. Set up field outputs (S, E, U, RF, SDEG, STATUS, DMICRT)
5. Apply boundary conditions:
   - Fix_Left_X (left edge fixed in x)
   - Fix_Bottom_Y (bottom edge fixed in y)
   - Pull_Right_X (right edge displacement = 2.5% × L)
6. Create the Job (but NOT submit)

When complete, you'll see:

```
FINISH COMPLETE — Ready to Submit
...
  5. Click "Submit"
```

### Step 5.4 — Save again

Menu: **File → Save** (or **Ctrl+S**)

---

## 6. Submit the Job

### Step 6.1 — Switch to Job module

In the module dropdown, select **Job**.

### Step 6.2 — Open Job Manager

Click the **Job Manager** icon in the toolbar (or Menu: Job → Manager).

### Step 6.3 — Submit

In the Job Manager dialog:
1. Select your job (e.g. `val_090s`)
2. Click **Submit**
3. The status will change: Submitted → Running → Completed

### Step 6.4 — Monitor

- Click **Monitor** to see convergence progress
- Typical run time: 30-60 minutes per job
- If it diverges, see troubleshooting in MANUAL_COHESIVE_WORKFLOW.md §6

### Step 6.5 — Verify completion

When status shows **Completed**, the .odb file is ready at:
```
abaqus_jobs/<job_name>.odb
```

---

## 7. Post-Process (one command line step)

This step requires the command line because Abaqus Python odbAccess
works best in `abaqus python` mode:

```bash
abaqus python scripts/postprocess_odb.py --odb abaqus_jobs/val_090s.odb --job-name val_090s
```

This produces: `results/val_090s_summary.csv`

> **Alternative GUI method:** You can also open the .odb in CAE and use
> View > ODB Field Output to inspect SDEG, STATUS, stress fields visually.
> But for data extraction to CSV, the command line is required.

---

## 8. Repeat for All 8 Jobs

For each job, repeat Steps 2-7:

| # | Job Name | Layup | t90 (µm) | Figures |
|---|----------|-------|----------|---------|
| 1 | `val_090s`   | [0/90]ₛ    | 250 | 5, 6, 9, 11a |
| 2 | `val_0902s`  | [0/90₂]ₛ   | 250 | 5, 6, 9, 11a |
| 3 | `val_0904s`  | [0/90₄]ₛ   | 250 | 5, 6, 8 |
| 4 | `pn_090n0`   | [0/90/0]   | 250 | 9, 11a |
| 5 | `pt_t90_020` | [0/90/0]   | 20  | 10, 11b |
| 6 | `pt_t90_060` | [0/90/0]   | 60  | 10, 11b |
| 7 | `pt_t90_100` | [0/90/0]   | 100 | 10, 11b |
| 8 | `pt_t90_140` | [0/90/0]   | 140 | 10, 11b |

> **Tip:** You can keep CAE open between jobs. After finishing one job
> (Steps 2-7), create a new model for the next job:
> Menu: Model → Create New Model
> Then run gui_build.py again with the next job name.

---

## 9. Plot All Figures (command line)

After all 8 jobs are post-processed (8 CSV files in `results/`):

```bash
python3 scripts/plot_figures.py --figures 5,9,10,11
```

This produces:
- `results/figure_05.png` (stress-strain + stiffness degradation)
- `results/figure_09.png` (ply number study)
- `results/figure_10.png` (ply thickness study)
- `results/figure_11.png` (crack density)

---

## 10. Troubleshooting

### Issue: "File → Run Script" doesn't show gui_build.py

**Fix:** Navigate to the `damage2/scripts/` directory in the file browser.
The dialog filters by .py extension by default.

### Issue: Dialog doesn't appear

**Cause:** Some older Abaqus versions don't support `getInputs()` in Run Script mode.

**Fix:** Use the Python console instead:
1. Menu: View → Python Console (to open the console at the bottom)
2. Type:
   ```python
   import sys
   sys.path.append(r'C:\path\to\damage2\scripts')
   import gui_build
   gui_build.main()
   ```
3. The dialog should appear, or you can modify gui_build.py to use
   hardcoded values instead of getInputs.

### Issue: "Model-1 already exists" error

**Cause:** You ran gui_build.py without creating a new model first.

**Fix:**
1. Menu: Model → Create New Model (name it anything, e.g. Model-2)
2. Or: delete the existing Model-1 (right-click in model tree → Delete)
3. Re-run gui_build.py

### Issue: Build script fails partway through

**Cause:** Various (mesh failure, partition failure, etc.)

**Fix:** Start fresh:
1. Menu: Model → Create New Model
2. File → Run Script → gui_build.py
3. Enter the job name

### Issue: Job fails to submit in Job Manager

**Fix:** Check the .dat and .msg files in `abaqus_jobs/`:
- `<job_name>.dat` contains the input file processor errors
- `<job_name>.msg` contains solver messages
- Look for "ERROR" lines

Common causes:
- Missing section assignment on cohesive elements
- BCs applied to wrong region
- Material orientation not set

### Issue: Want to start over completely

1. Close Abaqus/CAE (File → Exit)
2. Delete the .cae file:
   ```bash
   del abaqus_jobs\val_090s.cae
   ```
3. Reopen CAE and run gui_build.py again

---

## 11. Time Budget (GUI Workflow)

| Step | Per Job | All 8 Jobs |
|------|---------|------------|
| Open CAE + run gui_build.py | ~2 min | ~16 min |
| Manual cohesive insertion | ~5 min | ~40 min |
| Save + run gui_finish.py | ~1 min | ~8 min |
| Submit + wait for completion | ~1 hour | ~8 hours |
| Post-process (command line) | ~2 min | ~16 min |
| **Total manual effort** | **~8 min** | **~1 hour** |
| **Total wall-clock** | | **~9-10 hours** |

---

*Last updated: July 2026.*
