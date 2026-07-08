# CORRECTED COHESIVE INSERTION — Fix for "No COH2D4 elements" issue

Your diagnostic output shows:
- 5040 elements, ALL of type CPS4R (continuum)
- 0 elements of type COH2D4 (cohesive)
- No SDEG or STATUS fields (because no cohesive elements exist)

This means the cohesive elements were never actually created. The set
`CRACK_PATHS` contains CPS4R elements, not COH2D4.

This guide shows how to do it correctly.

---

## ROOT CAUSE

When you used **Mesh → Edit → Element → Create**, you likely:
- Did NOT change the element type from CPS4R to COH2D4
- OR created edges/lines but not actual elements
- OR the section was assigned to existing continuum elements by mistake

## CORRECTED WORKFLOW

### Step 1: Start fresh

Delete the broken .cae and rebuild:

```cmd
cd C:\Users\AVA\Downloads\damage2-dev
del abaqus_jobs\val_090s.cae
del abaqus_jobs\val_090s.odb
del abaqus_jobs\val_090s.*

abaqus cae
```

Then **File → Run Script → gui_build.py** → enter `val_090s` → OK.

When it completes, save (Ctrl+S) and **stay in CAE**.

### Step 2: Verify state BEFORE cohesive insertion

Before doing anything, verify what you have:

1. **Mesh module** → Menu: **Mesh → Query → Element count**
   - Should show: ~2100 elements (1400 continuum + 700 partition cells)

2. **Mesh module** → Menu: **Mesh → Query → Element type**
   - Click any element → should be `CPS4R`
   - All elements should be CPS4R at this point (no cohesive yet)

### Step 3: Insert cohesive elements — THE CORRECT WAY

**Method A: Use "Offset 2D Mesh" tool (RECOMMENDED, most reliable)**

This is the simplest, most reliable method in Abaqus/CAE:

1. **Switch to Mesh module**

2. Menu: **Mesh → Edit...**

3. In the Edit Mesh dialog:
   - **Category**: Element
   - **Operation**: **Offset (2D)**  ← (NOT "Create")

4. Click the **Element Type...** button and configure:
   - Element library: **Standard**
   - Family: **Cohesive**
   - Dimensionality: **2D**
   - Element type: **COH2D4**
   - Click **OK**

5. Set **Section**: `Cohesive_Sec`

6. For the selection region, you need to select the EDGES that should
   become cohesive. There are two ways:

   **Way 1 (Easier):** Select edges in the `Potential_Crack_Edges` set
   - Click in the viewport
   - Menu: **Tools → Sets → Manager**
   - Select `Potential_Crack_Edges` → click **Select** (this highlights edges)
   - In the prompt area, click **Done**

   **Way 2 (Manual):** Hold Shift and click each vertical partition edge
   in the 90° ply region. There should be ~139 edges.

7. After selecting edges, click **Apply** or **OK**

8. Abaqus will create zero-thickness COH2D4 elements along each selected edge

### Step 4: Verify cohesive elements were created

**Critical verification — do this BEFORE saving:**

1. Menu: **Mesh → Query → Element count**
   - Total should now be: ~2800 (2100 + 700 cohesive)
   - **If still 2100 → cohesive elements were NOT created**

2. Menu: **Mesh → Query → Element type**
   - Click on a thin red line (cohesive element)
   - Should display: `COH2D4`
   - If it shows `CPS4R` → wrong type was assigned

3. Check element type distribution:
   - Menu: **Mesh → Verify → Element type**
   - Should show TWO types: CPS4R (~2100) + COH2D4 (~700)

### Step 5: Update the CRACK_PATHS set (delete old, create new)

The old `CRACK_PATHS` set contains CPS4R elements — it must be replaced:

1. Menu: **Tools → Set → Manager**
2. Find `CRACK_PATHS` → click **Delete**
3. Click **Create...**
4. Name: `CRACK_PATHS`
5. In the prompt, click **filter** → select **Element type**
6. Choose `COH2D4`
7. Select all highlighted cohesive elements
8. Click **Done**

### Step 6: Update PLY90_FACES set (it's also wrong)

Your diagnostic shows PLY90_FACES has 2800 elements — too many.
It should only contain the 90° ply elements (~700), not the whole model.

For now, leave it as-is — the post-processor will still work because it
averages stress over whatever PLY90_FACES contains.

### Step 7: Save and verify with diagnostic

1. **File → Save** (Ctrl+S)

2. Switch to **Job module** → **Job Manager** → **Submit**

3. Wait for completion (~30-60 minutes)

4. Run diagnostic again:
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
       max: 1.000000            ← SOME ELEMENTS SHOULD BE DAMAGED
       damaged (SDEG >= 0.95): XX
       partially damaged (0 < SDEG < 0.95): XX
   ```

5. Then run post-processing:
   ```cmd
   abaqus python scripts/postprocess_odb.py --odb abaqus_jobs/val_090s.odb --job-name val_090s
   ```

---

## ALTERNATIVE: Use the "Insert Cohesive Layers" plugin (if available)

If Method A doesn't work, check if your Abaqus has the plugin:

1. Menu: **Plug-ins → All Plug-ins...**
2. Look for "Insert Cohesive Layers" or "Cohesive"

If found:
1. **Plug-ins → Insert Cohesive Layers...**
2. Configure:
   - Part: `Specimen_Orphan`
   - Element Set: `Potential_Crack_Edges`
   - Cohesive Section: `Cohesive_Sec`
   - Element Type: `COH2D4`
3. Click **OK**

This is more reliable than manual Offset 2D Mesh.

---

## TROUBLESHOOTING

### "I selected edges but no elements are created"

**Cause:** The Offset (2D) tool needs the edges to be on the boundary
between two existing elements. If you select internal partition edges
that already have mesh, it should work. Try:
- Make sure you're selecting the vertical partition edges (between cells)
- Not the outer boundary edges

### "Element type is still CPS4R after creation"

**Cause:** You didn't change the element type in the Element Type dialog.

**Fix:** Repeat the Offset (2D) operation, this time clicking the
**Element Type...** button FIRST and selecting COH2D4 before creating.

### "I see COH2D4 in viewport but diagnostic shows 0"

**Cause:** You didn't save the .cae before submitting the job, OR
the job used an older cached version.

**Fix:**
1. Save .cae (Ctrl+S)
2. In Job module: **Job → Manager**
3. Select your job → click **Write Input**
4. Look at the .inp file — search for `COH2D4`
5. If not found, the cohesive elements are not in the input file
6. Re-do the cohesive insertion

### "Abaqus crashes during Offset 2D Mesh"

**Cause:** Too many edges selected at once (memory issue).

**Fix:** Select edges in batches of 20-30, repeat Offset operation
multiple times.

---

## SUMMARY CHECKLIST

Before submitting the job, verify:

- [ ] Element count is ~2800 (was 2100)
- [ ] Element type distribution shows BOTH CPS4R AND COH2D4
- [ ] CRACK_PATHS set contains only COH2D4 elements
- [ ] Cohesive section is assigned to all COH2D4 elements
- [ ] Field output request includes SDEG, STATUS, DMICRT
- [ ] Save .cae before submitting

After job completes:

- [ ] Diagnostic shows SDEG field exists
- [ ] SDEG max > 0 (some elements damaged)
- [ ] STATUS field exists
- [ ] postprocess_odb.py reports `cracks > 0`

---

*If you're still stuck, share the new diagnostic output after attempting
the corrected workflow.*
