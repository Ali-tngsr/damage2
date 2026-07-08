# CORRECTED COHESIVE INSERTION — Using "Insert Cohesive Seams" tool

Your Abaqus version has a built-in **Insert cohesive seams** tool that
handles node duplication, element creation, and section assignment
automatically. This is the correct method to use.

---

## STEP-BY-STEP WORKFLOW

### Step 1: Start fresh (if you have a broken model)

```cmd
cd C:\Users\AVA\Downloads\damage2-dev
del abaqus_jobs\val_090s.cae
del abaqus_jobs\val_090s.odb
del abaqus_jobs\val_090s.*
abaqus cae
```

Then **File → Run Script → gui_build.py** → enter `val_090s` → OK.

When build completes, **Save (Ctrl+S)** and stay in CAE.

### Step 2: Verify the model is ready

Before inserting seams:

1. **Mesh module** → Menu: **Mesh → Query → Element count**
   - Should show: ~2100 elements (all CPS4R)
2. Menu: **Tools → Set → Manager**
   - Verify `Potential_Crack_Edges` set exists
   - Click it → click **Highlight** to see edges highlighted in viewport

### Step 3: Open the Edit Mesh tool

1. **Mesh module** → Menu: **Mesh → Edit...**
2. In the Edit Mesh dialog:
   - **Category**: select **Mesh** (NOT Element, NOT Node)
   - **Method**: select **Insert cohesive seams**

### Step 4: Configure Options

Click the **Settings...** button at the bottom of the Edit Mesh dialog.

In the Options dialog, you'll see:

**Section 1: "Create cohesive seam sets containing"**
- ✅ Elements → `CohesiveSeam-1-Elements` (keep checked, this is what we need)
- ✅ Top face nodes → `CohesiveSeam-1-TopNodes` (optional, keep checked)
- ✅ Bottom face nodes → `CohesiveSeam-1-BottomNodes` (optional, keep checked)
- ✅ Midside nodes → `CohesiveSeam-1-MidNodes` (optional, keep checked)

**Section 2: "Create cohesive seam surfaces containing"**
- ✅ Top element faces → `CohesiveSeam-1-TopSurf` (optional, keep checked)
- ✅ Bottom element faces → `CohesiveSeam-1-BottomSurf` (optional, keep checked)

Click **OK** to close Options.

### Step 5: Select element edges to insert seams

This is the critical step. The "Insert cohesive seams" tool asks you to
select **element edges** where the seams should be inserted. These must
be the vertical partition edges in the 90° ply.

**Method A: Use the pre-built set (recommended)**

1. After clicking in the viewport, the prompt area says "Select the
   element edges to define the seam"
2. From the selection toolbar (top of viewport), click the **Sets** button
   (or use menu: Tools → Sets → Manager)
3. In the Set Manager, select **`Potential_Crack_Edges`**
4. Click **Select** — this highlights all the edges in the set
5. The edges should now be selected in the viewport
6. Click **Done** in the prompt area

**Method B: Manual selection (fallback if set doesn't work)**

1. Make sure the selection filter is set to "Edges" (top toolbar)
2. Hold **Shift** and click each vertical partition edge in the 90° ply
3. There should be ~139 vertical edges
4. Click **Done** when finished

### Step 6: Verify cohesive elements were created

**Critical verification — do this BEFORE saving:**

1. Menu: **Mesh → Query → Element count**
   - Total should now be: ~2800 (2100 + 700 cohesive)
   - **If still 2100 → seams were NOT created, retry**

2. Menu: **Mesh → Query → Element type**
   - Click on a thin red line (cohesive element)
   - Should display: `COH2D4`
   - If it shows `CPS4R` → wrong type, retry

3. Check element type distribution:
   - Menu: **Mesh → Verify → Element type**
   - Should show TWO types: CPS4R (~2100) + COH2D4 (~700)

4. Check that section is assigned:
   - Menu: **Tools → Set → Manager**
   - You should see a new set: `CohesiveSeam-1-Elements`
   - Highlight it — the cohesive elements should highlight

### Step 7: Assign cohesive section to COH2D4 elements (CRITICAL)

The Insert cohesive seams tool may NOT automatically assign the cohesive
section. You must verify and assign manually:

1. Switch to **Property module**
2. Menu: **Section → Assign**
3. In the prompt, select **by element type** filter
4. Choose `COH2D4` as the filter
5. Select all highlighted COH2D4 elements
6. Click **Done**
7. In the section selection dialog, choose **`Cohesive_Sec`**
8. Click **OK**

Alternative: do this from Mesh module:
1. **Mesh module** → Menu: **Mesh → Element Type**
2. Select all COH2D4 elements (filter by type)
3. In the Element Type dialog:
   - Element library: Standard
   - Family: Cohesive
   - Dimensionality: 2D
   - Element type: **COH2D4**
4. Section: **Cohesive_Sec**
5. Click **OK**

### Step 8: Update CRACK_PATHS set

The post-processor looks for a set called `CRACK_PATHS` containing the
cohesive elements. The Insert cohesive seams tool created a set called
`CohesiveSeam-1-Elements` instead. You have two options:

**Option A: Rename the set (easier)**
1. Menu: **Tools → Set → Manager**
2. Find `CohesiveSeam-1-Elements` → click **Edit...**
3. Rename to `CRACK_PATHS` (or)
4. Click **Copy...** → name it `CRACK_PATHS`

**Option B: Create new set**
1. Delete the old `CRACK_PATHS` set (it contains wrong CPS4R elements)
2. Click **Create...**
3. Name: `CRACK_PATHS`
4. Filter by element type: `COH2D4`
5. Select all highlighted cohesive elements
6. Click **Done**

### Step 9: Verify field output requests include SDEG/STATUS

1. Switch to **Step module**
2. Menu: **Output → Field Output Requests → Manager**
3. Edit the F-Output-1 request
4. Verify these variables are selected:
   - S (Stress)
   - E (Strain)
   - U (Displacement)
   - RF (Reaction force)
   - **SDEG** (Stiffness degradation — critical for cohesive)
   - **STATUS** (Cohesive element status — critical)
   - **DMICRT** (Damage initiation criteria)
5. Click **OK**

If SDEG/STATUS are missing, add them now.

### Step 10: Save and submit

1. **File → Save** (Ctrl+S)
2. **File → Run Script → gui_finish.py** → enter `val_090s` → OK
3. Save again (Ctrl+S) — the finish script added BCs and Job
4. Switch to **Job module**
5. **Job Manager** → select `val_090s` → **Submit**
6. Wait for completion (~30-60 minutes)

### Step 11: Verify with diagnostic

```cmd
abaqus python scripts/diagnose_odb.py --odb abaqus_jobs/val_090s.odb
```

**Expected good output:**

```
--- ELEMENT TYPE DISTRIBUTION ---
  Instance: SPECIMEN_INST
    CPS4R: 2100 elements
    COH2D4: 700 elements     ← MUST SEE THIS

--- SDEG CHECK (last frame) ---
  Step Step-1: SDEG has 700 values
    min: 0.000000
    max: 1.000000
    damaged (SDEG >= 0.95): XX     ← SHOULD BE > 0
    partially damaged: XX

--- STATUS CHECK (last frame) ---
  Step Step-1: STATUS has 700 values
    open (STATUS < 1): XX          ← SHOULD BE > 0
    closed (STATUS >= 1): XX
```

### Step 12: Post-process

```cmd
abaqus python scripts/postprocess_odb.py --odb abaqus_jobs/val_090s.odb --job-name val_090s
```

**Expected output:**
```
Final state: XX cracks (normalized density = 0.XXX)
```

The crack count should be > 0.

---

## COMMON ISSUES WITH "INSERT COHESIVE SEAMS"

### Issue: "Cannot select edges — they don't appear in selection"

**Cause:** The edges must be **shared between two elements**. If they
are partition edges that haven't been meshed through, they can't be
selected.

**Fix:**
1. First, verify the mesh exists on both sides of the partition
2. Menu: View → Display Group → Show All
3. Try again

### Issue: "Insert seams created elements but they have wrong section"

**Cause:** The tool uses whatever cohesive section is "active" or it
creates a default one.

**Fix:** Follow Step 7 above to manually assign `Cohesive_Sec` to all
COH2D4 elements.

### Issue: "No cohesive elements visible after running tool"

**Cause:** The tool needs you to select edges, not faces. The prompt
in the bottom-left should say "Select element edges..."

**Fix:**
1. Make sure the selection filter at the top of the viewport is set to "Edges"
2. Hold Shift and click each vertical edge
3. Done

### Issue: "Cohesive elements exist but no SDEG in ODB"

**Cause:** Either:
- Section not assigned (Step 7 not done)
- Field output doesn't request SDEG (Step 9 not done)
- Job didn't actually damage them (maybe strength too high)

**Fix:**
1. Re-check section assignment
2. Re-check field output requests
3. Open .odb in CAE → check S11 stress on COH2D4 elements
   - If stress > 17 MPa and SDEG = 0 → section is wrong
   - If stress < 17 MPa → loading is insufficient

---

## VERIFICATION CHECKLIST

Before submitting the job:

- [ ] Element count is ~2800 (was 2100)
- [ ] Element type distribution shows BOTH CPS4R AND COH2D4
- [ ] `CohesiveSeam-1-Elements` set exists and contains COH2D4 elements
- [ ] `CRACK_PATHS` set contains only COH2D4 elements (renamed or copied)
- [ ] Section `Cohesive_Sec` is assigned to all COH2D4 elements
- [ ] Field output requests include SDEG, STATUS, DMICRT
- [ ] Save .cae before submitting

After job completes:

- [ ] Diagnostic shows COH2D4 elements exist
- [ ] Diagnostic shows SDEG field exists
- [ ] SDEG max > 0 (some elements damaged)
- [ ] STATUS field exists
- [ ] postprocess_odb.py reports `cracks > 0`

---

*This workflow uses the correct "Insert cohesive seams" tool that your
Abaqus version provides. It handles node duplication, element creation,
and (optionally) section assignment automatically.*
