# ABAQUS VISUALIZATION & SCREENSHOT GUIDE

This guide explains how to set up Abaqus/CAE visualization and capture
publication-quality screenshots for Figures 4, 6, 7, and 8.

---

## FIGURE 4 — Stochastic Mesoscale Model Overview

**Goal**: Show the partitioned mesh with Vf-based color mapping and one
highlighted cohesive crack path column (red).

### Step 1: Open the .odb (or .cae)

```cmd
abaqus cae database=abaqus_jobs\val_0904s.odb
```

(Use val_0904s because it has the most 90° plies — best for showing
the stochastic Vf distribution.)

### Step 2: Switch to Visualization module

In the module dropdown (top-left), select **Visualization**.

### Step 3: Display the undeformed model

1. Menu: **View → Display Options...**
2. In the **Basic** tab:
   - **Deformation**: select **Undeformed**
   - **Visible edges**: select **All edges** (or "Feature edges")
3. OK

### Step 4: Show Vf-based color mapping

The model doesn't have a "Vf" field by default. We need to show the
materials assignment as colors:

1. Menu: **View → Display Options...**
2. Go to **Color & Visibility** tab
3. In the **Element** section:
   - Set color by: **Material**
   - This will color elements by their assigned material

Alternative: Show mesh with different colors per section:
1. Menu: **View → Display Options...**
2. **Mesh** tab → check **Show mesh**
3. Set color by: **Section**

### Step 5: Highlight one cohesive crack path

1. Menu: **Tools → Display Group → Create...**
2. Select **Element sets**
3. Find a set like `CohesiveSeam-1-Elements` (or any crack path set)
4. Click **Replace** to show only cohesive elements
5. Change their color to red:
   - Menu: **View → Display Options → Color & Visibility**
   - Set cohesive element color to **Red**

6. Then click **Add** to also show the rest of the model in gray

### Step 6: Set view orientation

1. Menu: **View → Views Toolbar**
2. Click **Front** view (X-Y plane)
3. Menu: **View → Fit View** (or Ctrl+F) to fit model to screen

### Step 7: Capture screenshot

**Method A: Built-in PNG export (RECOMMENDED)**
1. Menu: **File → Print...**
2. In Print dialog:
   - **Destination**: select **File**
   - **File name**: `figure_04.png`
   - **Format**: PNG
   - **Resolution**: 300 DPI
   - **Image size**: 1920×1080 (or larger)
3. Click **OK**

**Method B: Screenshot tool**
- Windows: **Win + Shift + S** → select viewport → save as PNG
- Or use **Snipping Tool**

---

## FIGURE 6 — Crack Morphology at 2.5% Strain (4 panels)

**Goal**: Show 4 panels side-by-side: [0/90]s, [0/902]s, [0/904]s, [0/90/0]
each at 2.5% strain, with SDEG (damage) field visible.

### Step 1: Open each .odb in turn

For each of: `val_090s.odb`, `val_0902s.odb`, `val_0904s.odb`, `pn_090n0.odb`:

```cmd
abaqus cae database=abaqus_jobs\val_090s.odb
```

### Step 2: Switch to Visualization module

### Step 3: Go to the last frame (2.5% strain)

1. In the viewport toolbar, find the **Frame** dropdown (top of screen)
2. Select the **last frame** (should be at strain = 2.5%)
3. Or use the **Step/Frame** dialog: Menu: **Result → Step/Frame...**
4. Select the last frame → OK

### Step 4: Plot SDEG field

1. Menu: **Result → Field Output...**
2. In the dialog:
   - **Primary Variable**: select **SDEG** (Stiffness Degradation)
   - **Component**: select **INV** (invariant) or single component
3. Click **OK**

### Step 5: Show deformed shape

1. Menu: **View → Display Options...**
2. **Basic** tab:
   - **Deformation**: select **Deformed**
   - **Deformation scale factor**: select **Uniform**
   - **Value**: 5.0 (5x magnification to see cracks clearly)
3. OK

### Step 6: Set color scale

1. Menu: **View → Display Options → Color & Visibility**
2. **Contour** tab:
   - **Contour type**: Banded
   - **Color**: Spectrum (blue → red)
   - **Limits**: 0 to 1 (SDEG range)
3. OK

### Step 7: Capture screenshot

Save as: `figure_06_panel_<layup>.png` (e.g., `figure_06_panel_090s.png`)

### Step 8: Combine 4 panels into one image

Use any image editor (PowerPoint, Photoshop, GIMP, even Python):
1. Open all 4 screenshots
2. Arrange in 2×2 grid
3. Add labels: (a) [0/90]s, (b) [0/902]s, (c) [0/904]s, (d) [0/90/0]
4. Save as `figure_06.png`

---

## FIGURE 7 — Thin-Ply Crack Morphology (only 90° plies)

**Goal**: Same as Fig. 6 but only show 90° plies (hide 0° plies).

### Step 1: Open the thin-ply .odb files

For: `pt_t90_020.odb`, `pt_t90_060.odb`, `pt_t90_100.odb`, `pt_t90_140.odb`

### Step 2: Repeat Steps 2-6 from Figure 6

### Step 3: Hide 0° plies

1. Menu: **Tools → Display Group → Create...**
2. Select **Element sets**
3. Find the set `PLY90_FACES`
4. Click **Replace** to show only 90° ply elements
5. The 0° plies will disappear

### Step 4: Capture and combine as in Figure 6

---

## FIGURE 8 — Sequential Crack Propagation

**Goal**: Show [0/904]s at multiple strain levels (e.g., 0.5%, 1.0%, 1.5%, 2.0%, 2.5%).

### Step 1: Open val_0904s.odb

```cmd
abaqus cae database=abaqus_jobs\val_0904s.odb
```

### Step 2: Switch to Visualization module

### Step 3: Plot SDEG field (same as Fig. 6, Steps 4-6)

### Step 4: Capture multiple frames

For each frame (strain level):
1. Use **Result → Step/Frame...** to select the frame
   - Frame at 0.5% strain (~frame 5)
   - Frame at 1.0% strain (~frame 10)
   - Frame at 1.5% strain (~frame 15)
   - Frame at 2.0% strain (~frame 20)
   - Frame at 2.5% strain (last frame)
2. Menu: **File → Print → File** → save as `figure_08_strain_0p5.png`, etc.

### Step 5: Combine frames into one image

Arrange 5-6 frames in a row (or 2×3 grid) with strain labels:
```
[0.5%]  [1.0%]  [1.5%]  [2.0%]  [2.5%]
```

Save as `figure_08.png`

---

## GENERAL VISUALIZATION TIPS

### Tip 1: Better Color Spectrum

Default Abaqus spectrum goes from blue (low) to red (high). For SDEG:
- Blue (0.0) = undamaged
- Red (1.0) = fully damaged (crack)

To customize:
1. Menu: **View → Display Options → Color & Visibility**
2. **Contour** tab → **Spectrum** → choose "User-defined"
3. Set:
   - 0.0: Blue
   - 0.5: Green
   - 1.0: Red

### Tip 2: Hide Mesh Lines for Cleaner Look

1. Menu: **View → Display Options**
2. **Basic** tab:
   - **Visible edges**: select **Feature edges** (or "No edges")
3. This shows only the colored contour without mesh clutter

### Tip 3: Add Scale Bar / Coordinate System

1. Menu: **Viewport → Viewport Annotations...**
2. Check:
   - **Triad** (shows X-Y-Z axes)
   - **Scale bar**
3. Customize position and size

### Tip 4: High-Resolution Export

For publication quality (300 DPI):
1. Menu: **File → Print...**
2. Set:
   - Resolution: **300 DPI**
   - Image size: **1920×1080** or larger
   - Format: **PNG** (lossless)
3. Avoid JPEG — compression artifacts visible

### Tip 5: Consistent View Across Figures

For all figures, use the same view orientation:
1. Menu: **View → Views Toolbar**
2. Always click **Front** (X-Y plane)
3. Use **Fit View** (Ctrl+F) for consistent framing
4. Save view: **View → Save View...** → name it "paper_view"
5. Load saved view in other .odb files

### Tip 6: Hide Title Block

Abaqus shows a title block at top of viewport. To hide:
1. Menu: **Viewport → Viewport Annotations...**
2. Uncheck **Title block**
3. Uncheck **State block** (if you want cleaner look)

---

## RECOMMENDED WORKFLOW

### For Figures 6, 7 (4-panel layouts):

1. Create a PowerPoint or Word document
2. Set page size to landscape
3. Insert 4 screenshots in a 2×2 grid
4. Add labels: (a), (b), (c), (d) with layup names
5. Add scale bar annotation
6. Export as PNG: **File → Save As → PNG**

### For Figure 8 (sequential frames):

1. Same approach but 5-6 frames in a single row
2. Add strain % labels under each frame
3. Export as PNG

### For Figure 4 (model overview):

Single image, no grid needed. Just save with high resolution.

---

## CHECKLIST PER FIGURE

### Figure 4:
- [ ] Open val_0904s.odb
- [ ] Show undeformed shape
- [ ] Color by material/section
- [ ] Highlight one cohesive column in red
- [ ] Front view, fit to screen
- [ ] Export 300 DPI PNG

### Figure 6:
- [ ] Open each of 4 .odb files (val_090s, val_0902s, val_0904s, pn_090n0)
- [ ] For each:
  - [ ] Go to last frame (2.5% strain)
  - [ ] Plot SDEG field
  - [ ] Show deformed shape (5x scale)
  - [ ] Hide 0° plies (use PLY90_FACES set)
  - [ ] Capture PNG
- [ ] Combine 4 PNGs into 2×2 grid

### Figure 7:
- [ ] Open each of 4 thin-ply .odb files (pt_t90_020, _060, _100, _140)
- [ ] Same as Fig. 6 but show only 90° plies (hide 0°)
- [ ] Combine 4 PNGs into 2×2 grid

### Figure 8:
- [ ] Open val_0904s.odb
- [ ] Plot SDEG
- [ ] Capture at 5-6 different strain levels
- [ ] Arrange in a row with strain labels

---

## TIME ESTIMATE

| Figure | Time |
|--------|------|
| Fig. 4 | 15 min |
| Fig. 6 | 45 min (4 panels × ~10 min each) |
| Fig. 7 | 45 min |
| Fig. 8 | 30 min (5-6 frames) |
| **Total** | **~2.5 hours** |

---

*Good luck! These screenshots complete your replication of all 11 paper figures.*
