# Replication & Extension Plan

**Paper:** *Unraveling Transverse Crack Multiplication in Thin-Ply Orthotropic Laminates: A Stochastic Finite Element Study*
**Authors:** Rumayshah, Wicaksono, Wirawan, Dirgantara, Judawisastra, Pulungan (Institut Teknologi Bandung)
**Journal:** Mechanics of Advanced Materials and Structures — Manuscript ID: UMCM-2025-1979.R1
**Extension Proposal Provided:** ❌ None — Extension section is skipped per instructions.

---

## 0. Repository Structure

This repository is a refactored fork of `Ali-tngsr/Damage`. All Abaqus scripts are Python 2.7 compatible.

```
damage2/
├── README.md                       # This document
├── data/
│   └── table1_properties.csv       # Homogenized properties for Vf = 0..90%
├── scripts/
│   ├── config.py                   # Central configuration (geometry, layups, mesh)
│   ├── material_table.py           # Table 1 data + interpolation helpers
│   ├── material_interp.py          # Property interpolation (numpy + pure-python)
│   ├── vf_field.py                 # Stochastic Vf field generator
│   ├── mesoscale_common.py         # Shared helpers (assign_vf_field, get_properties, safe_name)
│   ├── build_mesoscale_model.py    # Build geometry, partitions, materials, edge sets
│   ├── Cohesive_Mat.py             # Cohesive material/section + continuum mesh
│   ├── Cohesive_Mat2.py            # Crack-path set creation
│   ├── OrphanMesh.py               # Convert to orphan mesh
│   ├── boundaryConditions.py       # Assembly, BCs, step, job creation
│   ├── postprocess_odb.py          # ODB extraction (stress, strain, SDEG, cracks)
│   ├── plot_results.py             # Matplotlib plotting helpers
│   ├── run_pipeline.py             # End-to-end Abaqus driver (CLI args supported)
│   └── run_all.py                  # Non-Abaqus utility runner (CSV/Vf preview)
├── abaqus_jobs/                    # Generated .cae / .odb / .inp (gitignored)
└── results/                        # Generated CSV / PNG (gitignored)
```

### Quick Start

```bash
# 1. Generate preview CSVs (no Abaqus required)
python scripts/run_all.py

# 2. Run the full Abaqus pipeline
abaqus cae noGUI=scripts/run_pipeline.py -- --submit

# 3. Custom parameters
abaqus cae noGUI=scripts/run_pipeline.py -- --t90=0.5 --rho-sat=8.0 --seed=42 --submit

# 4. Post-process the ODB
abaqus python scripts/postprocess_odb.py --odb path/to/job.odb
```

### Differences from `Ali-tngsr/Damage`

This repository adds:
- `config.py` — central parameter store (prevents magic numbers across scripts)
- `material_table.py` — Table 1 source of truth (was inline in `mesoscale_common`)
- `vf_field.py` — standalone Vf field generator (decoupled from Abaqus)
- `plot_results.py` — publication-quality plotting helpers
- `run_all.py` — non-Abaqus utility runner for quick preview
- `run_pipeline.py` — CLI argument support (`--L=`, `--t90=`, `--rho-sat=`, `--seed=`, `--submit`)
- `build_mesoscale_model.py` — automatic `Potential_Crack_Edges` set creation, input validation
- `boundaryConditions.py` — orphan-mesh-aware BCs using `nodes` instead of `edges`

---

## 1. Paper Deconstruction & Core Methodology

### 1.1 Architectural Overview

The paper implements a **two-scale, sequential (hierarchical) multiscale stochastic FE framework** in ABAQUS. The two scales are decoupled and executed in order:

```
[Optical Micrograph]
        │
        ▼
[Image Segmentation & Binarization] ──► Vf distribution map
        │
        ├──────────────────────────────────────────────┐
        ▼                                              ▼
[SCALE 1: Unit Cell Homogenization]       [SCALE 2: Stochastic Mesoscale FE]
  - Vf ∈ {0,15,30,45,60,75,90}%           - Orthotropic linear elastic elements
  - Drucker-Prager plasticity (PP)         - Properties ← Table 1 (interpolated)
  - Ductile damage (matrix cracking)       - Cohesive elements = potential crack paths
  - Cohesive elements (fiber debonding)    - Spatial Vf rules (interface vs. centerline)
  - Output → Table 1 (E11,E22,G12…)       - Load to 2.5% strain
        │                                              │
        └──────────────────────────────────────────────┘
                                                       │
                                                       ▼
                                         [Validation: Fig. 5 vs. experiment]
                                         [Parametric: Figs. 6–11]
```

> **Critical shortcut for replication:** Table 1 in the paper gives *all seven* homogenized property sets. This means **Scale 1 can be entirely bypassed** for the MVP — the output of Scale 1 is already published.

---

### 1.2 Primary Governing Equations & Mathematical Models

#### 1.2.1 Crack Path Seeding Formula

The number of cohesive column insertions (potential crack paths) in the mesoscale model:

$$n = \rho \times \frac{t_{90}}{L}$$

| Symbol | Definition | Source |
|--------|-----------|--------|
| $n$    | Number of cohesive crack-path columns | Equation in §2.2 |
| $\rho$ | Crack saturation value (cracks/mm, taken from Hu et al. [17]) | External reference |
| $t_{90}$ | Transverse (90°) ply thickness [mm] | Design parameter |
| $L$    | Specimen length [mm] = 70 mm (gauge) | §2.2 |

#### 1.2.2 Cohesive Zone Model (Bilinear Traction-Separation)

Each cohesive element follows a bilinear law:

- **Before damage initiation:**
  $T_n = K_n \cdot \delta_n$ where $K_n = 1 \times 10^8 \text{ MPa/mm}$ (uniform penalty stiffness)

- **Damage initiation** — Maximum Stress Criterion:
  $$\max\!\left(\frac{\langle t_n \rangle}{T_n^0},\; \frac{t_s}{T_s^0},\; \frac{t_t}{T_t^0}\right) = 1$$
  where $T_n^0 = Y_T$ (transverse tensile strength from the nearest mesoscale cell — spatially varied).

- **Damage evolution** — Linear softening governed by fracture energy:
  $$G_{c,MT} = \int_0^{\delta_f} T\, d\delta = \text{area under unit cell } \sigma\text{–}\varepsilon \text{ curve} \times l_{char}$$

- **Damage variable** after initiation:
  $$D = \frac{\delta_f(\delta_{max} - \delta_0)}{\delta_{max}(\delta_f - \delta_0)}, \quad D \in [0, 1]$$

#### 1.2.3 Volumetric-Averaged Stress (Post-Processing)

The reported transverse stress in the 90° ply is the volume-weighted average:

$$\bar{\sigma}_x^{90} = \frac{\sum_{i=1}^{N} \sigma_x^i \cdot v_i}{\sum_{i=1}^{N} v_i}$$

where $\sigma_x^i$ is the stress in the x-direction of element $i$ and $v_i$ is its volume.

#### 1.2.4 Normalized Stiffness Degradation

$$\hat{E}_{90}(\varepsilon_x) = \frac{E_{90}(\varepsilon_x)}{E_{90}^0}$$

where $E_{90}^0$ is the initial (undamaged) transverse modulus of the 90° ply.

#### 1.2.5 Normalized Crack Density

$$\rho_{norm} = \frac{\text{number of fully propagated cracks}}{\rho_{sat}}$$

A crack is counted only after it has propagated more than **half the transverse ply thickness**. Saturation ($\rho_{sat}$) is used for normalization, sourced from Hu et al. [17].

#### 1.2.6 Hyperbolic Drucker-Prager Yield Function (Scale 1 only)

Used for the PP matrix in the unit cell; not needed if bypassing Scale 1:

$$F = \sqrt{q^2 + (p \tan\beta)^2} - (d - p\tan\beta) = 0$$

where $q$ = von Mises stress, $p$ = hydrostatic pressure, $\beta$ = friction angle, $d$ = cohesion.

---

### 1.3 Exact Baseline Parameters & Material Properties

#### Material: GF/PP, Ply thickness = 255 µm, $V_f$ = 45% (nominal)

**Table 1 — Homogenized Properties (directly usable, no Scale 1 needed):**

| $V_f$ (%) | $E_{11}$ (GPa) | $\nu_{12}$ | $E_{22}$ (GPa) | $\nu_{23}$ | $Y_T$ (MPa) | $G_{12}$ (GPa) | $G_{23}$ (GPa) |
|-----------|---------------|------------|---------------|------------|-------------|----------------|----------------|
| 0         | 1.70          | 0.40       | 1.70          | 0.40       | 20          | 0.61           | 0.61           |
| 15        | 12.20         | 0.64       | 2.48          | 0.34       | 19          | 0.81           | 0.78           |
| 30        | 22.73         | 0.59       | 3.25          | 0.34       | 18          | 1.09           | 1.02           |
| 45        | 33.29         | 0.54       | 4.45          | 0.32       | 17          | 1.51           | 1.43           |
| 60        | 43.80         | 0.49       | 6.59          | 0.28       | 16          | 2.21           | 2.21           |
| 75        | 54.31         | 0.45       | 10.89         | 0.23       | 15          | 3.68           | 3.90           |
| 90        | 64.85         | 0.40       | 17.98         | 0.16       | 14          | 6.15           | 6.80           |

> For intermediate $V_f$ values: use **piecewise linear interpolation** between the tabulated rows.

**Specimen Geometry (§2.2):**

| Parameter | Value |
|-----------|-------|
| Specimen total length | 110 mm |
| Gauge length ($L$) | 70 mm |
| Width | 20 mm |
| [0/90]s thickness | 1.0 mm |
| [0/90₂]s thickness | 1.5 mm |
| [0/90₄]s thickness | 2.5 mm |
| 0° ply thickness | 250 µm (constant in parametric study) |
| 90° ply thickness (parametric) | 20, 60, 100, 140 µm |

**Cohesive Element Properties:**

| Parameter | Value |
|-----------|-------|
| Penalty stiffness $K_n$ | $1 \times 10^8$ MPa/mm (uniform) |
| Strength $T_n^0$ | Spatially varied = local $Y_T$ from Table 1 |
| Fracture energy $G_{c,MT}$ | Area under unit cell $\sigma$–$\varepsilon$ curve × $l_{char}$ |
| Damage initiation | Maximum stress criterion |
| Damage evolution | Linear softening |

**Spatial Vf Distribution Rules (§2.2):**

- 90° ply divided into **5 sub-cells through the thickness**
- Cells adjacent to 0°/90° interfaces → **low $V_f$** (resin-rich)
- Cells at ply centerline → **high $V_f$** (fiber-rich)
- Distribution validated against experimental micrographs

**Applied Loading:**

- Uniaxial tensile strain along fiber direction of 0° plies
- Maximum applied strain: **2.5%**
- Boundary conditions: symmetric (roller + displacement control)

---

### 1.4 Recommended Software Stack

#### Option A — Faithful Replication (Recommended if ABAQUS licensed)

| Task | Tool |
|------|------|
| Mesoscale FE model generation | **ABAQUS 6.17+** with **Python 2.7/3.x scripting** (Abaqus/CAE Python API) |
| Model automation & stochastic assignment | **Python** (NumPy, random) inside Abaqus Python |
| Post-processing (stress, stiffness, crack density) | **Python 3** with NumPy, Pandas, Matplotlib |
| Piecewise interpolation of Table 1 | `scipy.interpolate.interp1d` or `numpy.interp` |
| Optical image binarization (if replicating full pipeline) | **Python** with `scikit-image` or `OpenCV` |

> ABAQUS is the only option for faithful replication because the paper uses ABAQUS-specific constitutive models (Drucker-Prager, ductile damage, cohesive surfaces) and its Python scripting API (`abaqus`, `abaqusConstants`, `odbAccess`).

#### Option B — Open-Source Alternative (If ABAQUS unavailable)

| Task | Tool |
|------|------|
| 2D mesoscale FE with cohesive elements | **FEniCS / dolfinx** (Python) with custom cohesive element formulation |
| Or: simplified spring-cohesive bar model | Pure **NumPy/SciPy** — treat each cohesive column as a spring with bilinear softening |
| Constitutive integration | Custom Python class per element |
| Post-processing | Matplotlib |

> ⚠️ **Warning:** A pure Python FEM from scratch is a significant undertaking. The spring-bar analogy (1D array of elements with cohesive springs) is the fastest open-source approximation but sacrifices spatial 2D stress gradients.

#### Option C — Minimal Reproducibility Baseline

Use the **published data** (Table 1 + experiment figures) to implement a simplified analytical model (e.g., shear-lag or COD-based crack density model) that reproduces the trend in Fig. 11a. This is valid for demonstrating conceptual understanding but is not a numerical replication.

**Verdict for University Project:** Use **Option A** if ABAQUS is available (most common in aerospace/mechanical engineering departments). This plan is structured around Option A with notes for Option B where applicable.

---

## 2. Minimum Viable Replication (MVP) Plan

### 2.1 Primary Target: Figure 5 (Validation Result)

Figure 5 is the paper's central validation — it compares:
- **(a)** Stress-strain curves for [0/90]s, [0/902]s, [0/904]s vs. experiment
- **(b)** 90° ply stiffness degradation $E_{90}(\varepsilon_x)$ vs. experiment

Reproducing Fig. 5 constitutes a **complete MVP**.

### 2.2 What Can Be Safely Ignored (Time Savers)

| Section / Component | Justification for Skipping |
|--------------------|-----------------------------|
| **Scale 1 (Unit Cell Homogenization)** | All outputs (Table 1) are directly published — no re-simulation needed |
| Drucker-Prager plasticity model | Only needed for Scale 1 |
| Fiber-matrix cohesive debonding at micromechanics level | Only needed for Scale 1 |
| Micrograph image processing & binarization | Can use the published Vf distribution rules described in §2.2 directly |
| Figures 6, 7, 8 (damage morphology visualizations) | Qualitative only; not needed for quantitative validation |
| Parametric study (Figs. 9–11) | Do only after Fig. 5 is validated; add as time permits |
| Void inclusion | Explicitly stated as a future work item; not in current model |

### 2.3 Step-by-Step Implementation Phases

---

#### Phase 0: Environment Setup (Day 1, ~2–3 hours)

- [ ] Verify ABAQUS license and version (≥ 6.17 recommended)
- [ ] Set up a working directory with a structured folder layout:
  ```
  project/
  ├── data/
  │   └── table1_properties.csv      # Transcribe Table 1
  ├── scripts/
  │   ├── material_interp.py         # Property interpolation
  │   ├── build_mesoscale_model.py   # Abaqus Python script
  │   └── postprocess_odb.py         # ODB extraction
  ├── abaqus_jobs/
  └── results/
  ```
- [ ] Transcribe Table 1 into `table1_properties.csv` (7 rows × 8 columns)
- [ ] Write and test `material_interp.py`:
  ```python
  import numpy as np
  
  Vf_data = np.array([0, 15, 30, 45, 60, 75, 90])
  E11 = np.array([1.70, 12.20, 22.73, 33.29, 43.80, 54.31, 64.85])
  E22 = np.array([1.70, 2.48, 3.25, 4.45, 6.59, 10.89, 17.98])
  nu12 = np.array([0.40, 0.64, 0.59, 0.54, 0.49, 0.45, 0.40])
  nu23 = np.array([0.40, 0.34, 0.34, 0.32, 0.28, 0.23, 0.16])
  YT   = np.array([20.0, 19.0, 18.0, 17.0, 16.0, 15.0, 14.0])
  G12  = np.array([0.61, 0.81, 1.09, 1.51, 2.21, 3.68, 6.15])
  G23  = np.array([0.61, 0.78, 1.02, 1.43, 2.21, 3.90, 6.80])
  
  def get_properties(Vf_target):
      props = {}
      for name, arr in zip(['E11','E22','nu12','nu23','YT','G12','G23'],
                           [E11, E22, nu12, nu23, YT, G12, G23]):
          props[name] = float(np.interp(Vf_target, Vf_data, arr))
      return props
  ```

---

#### Phase 1: Stochastic Vf Field Generator (Day 1–2, ~4 hours)

This is the **stochasticity engine** of the model. Implement the spatial Vf assignment rules from §2.2.

- [ ] Define the 90° ply mesh geometry: `n_cols` × 5 cells (5 rows through thickness, `n_cols` along length)
- [ ] Implement the spatial distribution rule:
  ```python
  import numpy as np
  
  def assign_vf_field(n_cols, n_rows=5, seed=None):
      """
      Assign Vf to each mesoscale cell following physical rules:
      - Rows 0 and 4 (interface cells): low Vf (resin-rich, ~0–30%)
      - Rows 2 (centerline): high Vf (fiber-rich, ~45–75%)
      - Rows 1 and 3 (transition): intermediate
      Rules calibrated to match micrograph statistics.
      """
      rng = np.random.default_rng(seed)
      vf_field = np.zeros((n_rows, n_cols))
      
      # Interface rows (resin-rich boundary)
      vf_field[0, :] = rng.uniform(0, 30, n_cols)
      vf_field[4, :] = rng.uniform(0, 30, n_cols)
      # Transition rows
      vf_field[1, :] = rng.uniform(20, 55, n_cols)
      vf_field[3, :] = rng.uniform(20, 55, n_cols)
      # Centerline (fiber-rich core)
      vf_field[2, :] = rng.uniform(45, 75, n_cols)
      
      return vf_field
  ```
  > ⚠️ **Note:** The exact Vf ranges per row are NOT explicitly given in the paper. The ranges above are physically motivated approximations. Calibrate by matching the aggregate Vf distribution to the nominal 45% and checking histograms match Fig. 2a qualitatively.

- [ ] For each cell, call `get_properties(Vf)` to retrieve its material constants and cohesive strength $Y_T$.

---

#### Phase 2: Mesoscale FE Model in ABAQUS (Day 2–4, ~1–2 days)

This is the most time-intensive phase. Use the ABAQUS Python scripting API.

- [ ] **Define specimen geometry** in the 2D ABAQUS sketch:
  - Width (x-direction): 70 mm (gauge length)
  - Height (y-direction): total laminate thickness (e.g., 1 mm for [0/90]s)
  - 0° plies: homogeneous isotropic or orthotropic elastic (use 45% Vf properties from Table 1)
  - 90° ply: 5 sub-layers in y, `n_cols` cells in x

- [ ] **Compute number of crack path columns** using the formula:
  ```python
  rho_sat = 8.0   # cracks/mm — obtain from Hu et al. [17], calibrate to match Fig. 11
  t90 = 0.255     # ply thickness in mm (255 µm for validation case)
  L = 70.0        # gauge length in mm
  n_crack_paths = int(np.round(rho_sat * t90 / L * L))
  # Simplification: n = rho_sat * t90 gives paths per mm, then scale to model length
  n_cols = int(np.round(rho_sat * L))
  ```
  > The paper defines n relative to the full specimen length. Calibrate `rho_sat` from the experimental crack density at saturation in Fig. 11.

- [ ] **Insert cohesive elements** as zero-thickness element columns at regular intervals along x:
  - Element type: `COH2D4` (2D 4-node cohesive) in ABAQUS
  - Placed **between** the orthotropic continuum elements at each potential crack path column
  - Assign cohesive properties per column from the local $Y_T$ of adjacent cells

- [ ] **Assign material properties** to each continuum element section:
  ```python
  # Pseudocode for Abaqus Python API
  for col_idx in range(n_cols):
      for row_idx in range(5):
          vf = vf_field[row_idx, col_idx]
          props = get_properties(vf)
          # Create orthotropic elastic material
          mdb.models['Model-1'].Material(name=f'mat_r{row_idx}_c{col_idx}')
          mdb.models['Model-1'].materials[f'mat_r{row_idx}_c{col_idx}'].Elastic(
              type=ENGINEERING_CONSTANTS,
              table=((props['E11']*1e3, props['E22']*1e3, props['E22']*1e3,
                      props['nu12'], props['nu23'], props['nu12'],
                      props['G12']*1e3, props['G23']*1e3, props['G12']*1e3),)
          )
  ```

- [ ] **Assign cohesive section properties:**
  ```python
  # For each cohesive column at position col_idx:
  YT_local = props_left['YT']  # from adjacent cell
  Gc_MT = 0.5 * YT_local * delta_f  # estimated; calibrate from unit cell curves
  K_penalty = 1e8  # MPa/mm
  mdb.models['Model-1'].Material(name=f'coh_{col_idx}')
  mdb.models['Model-1'].materials[f'coh_{col_idx}'].Elastic(
      type=TRACTION, table=((K_penalty, K_penalty, K_penalty),))
  mdb.models['Model-1'].materials[f'coh_{col_idx}'].MaxsDamageInitiation(
      table=((YT_local, YT_local*0.5, YT_local*0.5),))
  mdb.models['Model-1'].materials[f'coh_{col_idx}'].DamageEvolution(
      type=ENERGY, table=((Gc_MT,),))
  ```

- [ ] **Define boundary conditions:**
  - Left edge: fixed in x (roller), free in y
  - Bottom edge: fixed in y (roller)
  - Top/Bottom free surfaces: traction-free
  - Right edge: displacement-controlled in x → target $u_x = 0.025 \times L = 1.75$ mm

- [ ] **Create and submit the ABAQUS job:**
  ```python
  mdb.Job(name='GF_PP_090s', model='Model-1').submit()
  ```

---

#### Phase 3: Post-Processing & Result Extraction (Day 4–5, ~4–6 hours)

- [ ] **Extract stress and displacement from ODB:**
  ```python
  from odbAccess import openOdb
  import numpy as np
  
  odb = openOdb('GF_PP_090s.odb')
  steps = odb.steps['Step-1']
  
  stress_x_avg = []
  stiffness = []
  
  for frame in steps.frames:
      sf = frame.fieldOutputs['S']   # Stress
      uf = frame.fieldOutputs['U']   # Displacement
      
      # Filter to 90-degree ply elements only
      s11_vals, vols = [], []
      for value in sf.values:
          if value.elementLabel in ply90_element_set:
              s11_vals.append(value.data[0])   # S11 = sigma_x
              vols.append(element_volumes[value.elementLabel])
      
      sigma_avg = np.dot(s11_vals, vols) / np.sum(vols)
      stress_x_avg.append(sigma_avg)
      # Stiffness from slope of global stress-strain
  ```

- [ ] **Compute global laminate stress:** reaction force / cross-sectional area
- [ ] **Compute E90:** slope of the 90° ply volumetric-averaged stress vs. applied strain
- [ ] **Count cracks:** after each frame, count cohesive columns where `SDEG > 0.5` (damage variable D) across more than half the ply thickness
- [ ] **Plot Fig. 5a (stress-strain):** overlay model vs. experimental data points (digitize from paper using WebPlotDigitizer if needed)
- [ ] **Plot Fig. 5b (stiffness degradation):** $E_{90}/E_{90}^0$ vs $\varepsilon_x$

---

#### Phase 4: Validation & Calibration (Day 5, ~3–4 hours)

- [ ] Compare peak stress levels against experimental data in Fig. 5a
- [ ] Check first crack strain (~0.35% per paper) appears in correct strain range
- [ ] If stiffness is overestimated (as acknowledged in paper for [0/902]s and [0/904]s), this is **expected and documented** — no need to fix
- [ ] Compare crack density saturation level against Fig. 11a
- [ ] **Calibration knobs** (in order of impact):
  1. `rho_sat` — adjusts number of crack paths and saturation density
  2. Vf range per thickness row — adjusts first crack onset strain
  3. `Gc_MT` — adjusts softening rate and stiffness degradation slope
  4. Mesh density — run a coarse mesh first, refine if needed

---

#### Phase 5: Parametric Study (Day 6+, ~1 day each)

Only pursue if Phase 4 is successfully completed.

- [ ] **Ply number study** (Fig. 9 & Fig. 11a): re-run for [0/90/0], [0/90]s, [0/902]s — only change laminate stacking and total thickness
- [ ] **Ply thickness study** (Fig. 10 & Fig. 11b): re-run for $t_{90}$ = 20, 60, 100, 140 µm — update geometry and crack path count $n$ accordingly

---

## 3. Extension Strategy

> **No extension proposal was provided.** This section is intentionally left as a placeholder per instructions. If a proposal is submitted later, this section will define:
> - How new variables or loading conditions integrate into the mesoscale ABAQUS Python script
> - Any required changes to the material subroutines or constitutive models
> - Potential solver instabilities introduced (e.g., snap-back under displacement control, cohesive element ill-conditioning)
> - Additional post-processing routines needed

**Suggested extension directions based on paper's own future work statements (for reference only):**

1. **Void inclusion:** Add void cells (0% Vf matrix-only regions) seeded probabilistically into the Vf field; study effect on first crack onset strain
2. **Off-axis loading:** Change loading direction from 0° (axial) to ±15°/±30°; requires updating boundary conditions and material orientations
3. **Fatigue loading:** Replace static displacement ramp with cyclic loading via ABAQUS amplitude definition; track crack density per cycle
4. **Delamination coupling:** Add cohesive elements at the 0°/90° interfaces (between plies) to capture the delamination-transverse crack interaction described in Fig. 5 discussion

---

## 4. Chronological Task Checklist

### Week 1 — Core Implementation

#### Day 1: Setup & Data Foundation

- [ ] Install/verify ABAQUS license; confirm Python scripting works (`abaqus python` command)
- [ ] Create project folder structure (see Phase 0)
- [ ] Transcribe Table 1 into `table1_properties.csv`
- [ ] Implement and unit-test `material_interp.py` — verify `get_properties(45)` returns values matching Table 1 row for 45%
- [ ] Install Python post-processing environment: `pip install numpy scipy matplotlib pandas`
- [ ] Digitize experimental data from Fig. 5a and 5b using WebPlotDigitizer (free, browser-based) — save as CSV files for later overlay plots

#### Day 2: Stochastic Field & Model Architecture

- [ ] Implement `assign_vf_field(n_cols, n_rows=5, seed)` function
- [ ] Plot histogram of generated Vf values to verify distribution shape (should peak around 45%)
- [ ] Prototype the ABAQUS Python script structure: geometry, partitions, mesh
- [ ] Build a **minimal test model** — single 90° cell with one cohesive column — to verify bilinear traction-separation law is working
- [ ] Confirm crack initiation occurs at reasonable stress level (should be near $Y_T$ at 45% Vf = 17 MPa)

#### Day 3: Full Mesoscale Model — [0/90]s First

- [ ] Build the full [0/90]s geometry (simplest configuration, 1 mm total thickness)
- [ ] Implement stochastic Vf assignment loop over all cells
- [ ] Insert cohesive columns at computed $n$ positions
- [ ] Assign all material sections and cohesive properties
- [ ] Apply boundary conditions (roller left/bottom, displacement right edge)
- [ ] Define load step: linear ramp to $\varepsilon_x = 2.5\%$ with ~200 increments
- [ ] Submit job and monitor convergence (watch for excessive increments in early cracking)

#### Day 4: Post-Processing Pipeline

- [ ] Write `postprocess_odb.py` to extract: (a) global stress-strain, (b) E90 per frame, (c) crack count per frame
- [ ] Run post-processing on [0/90]s job output
- [ ] Generate Fig. 5 overlay plots (model vs. digitized experiment)
- [ ] Check: Does first crack appear near 0.35% strain? Does [0/90]s fit the initial modulus region well (as stated in paper)?

#### Day 5: Calibration & Validation Confirmation

- [ ] If results are off: adjust `rho_sat`, Vf ranges, or `Gc_MT` (in that order)
- [ ] Run [0/902]s model (increase 90° ply count; expect slight modulus overestimation — this is documented in the paper and acceptable)
- [ ] Run [0/904]s model
- [ ] Generate complete Fig. 5a and 5b with all three configurations
- [ ] **MVP achieved** if all three configurations show qualitative agreement with experiment

### Week 2 — Consolidation & Parametric Study

#### Day 6: Ply Number Parametric Study (Fig. 9 & Fig. 11a)

- [ ] Run [0/90/0] simulation (single 90° ply, non-symmetric — adjust geometry accordingly)
- [ ] Ensure 0° ply properties use 45% Vf isotropic/orthotropic constants from Table 1
- [ ] Extract and plot: (a) averaged transverse stress vs. time, (b) normalized stiffness vs. strain
- [ ] Count cracks and plot normalized crack density vs. strain
- [ ] Compare trend: [0/90/0] should retain ~60% stiffness, [0/902]s should retain ~30% (per §3.3)

#### Day 7: Ply Thickness Parametric Study (Fig. 10 & Fig. 11b)

- [ ] Modify model geometry for $t_{90}$ = 20 µm — recalculate $n$ crack paths (will be fewer)
- [ ] Run for $t_{90}$ = 20, 60, 100, 140 µm
- [ ] Post-process and plot Fig. 10a (peak transverse stress) and 10b (stiffness degradation)
- [ ] Check: 20 µm case should show delayed stiffness degradation and crack saturation at higher strain (§3.4)
- [ ] Note: non-monotonic behavior (100 µm and 140 µm slightly higher peak stress) is expected due to stochastic randomness

#### Day 8: Figure Generation & Write-Up

- [ ] Finalize all plots using `matplotlib` with publication-quality settings (300 DPI, labeled axes, legend)
- [ ] Produce replicated versions of: Fig. 5, Fig. 9, Fig. 10, Fig. 11
- [ ] Write a brief replication notes document documenting:
  - Any calibration choices made (rho_sat, Gc_MT, Vf ranges)
  - Deviations from the paper (e.g., if 3D was simplified to 2D)
  - Convergence statistics (number of increments, job time)
- [ ] Archive all ABAQUS input files, Python scripts, and ODB files

#### Day 9–10: Buffer / Quality Assurance

- [ ] Perform a **mesh sensitivity check** on the [0/90]s model with a coarser and finer mesh; verify crack density and stiffness results are mesh-independent
- [ ] Run two additional random seeds on the stochastic model — verify results are statistically stable (small variation expected between seeds)
- [ ] Document which results showed good agreement and which showed the same limitations as noted in the paper (initial modulus overestimation for multi-ply cases)
- [ ] Prepare any required report sections or presentation slides from the generated figures

---

## Appendix A: Key Numerical Pitfalls & Debugging Guide

| Issue | Likely Cause | Fix |
|-------|-------------|-----|
| Job fails to converge in cracking region | Snap-back in cohesive softening | Reduce max increment size; enable stabilization |
| No cracks form at all | $Y_T$ too high or penalty stiffness too low | Check material assignment; reduce $Y_T$ or re-check Vf interpolation |
| All cohesive elements fail simultaneously | Missing stochastic variation (all cells same Vf) | Debug `assign_vf_field` — verify field is not uniform |
| Stiffness never degrades in Fig. 5b | Cracks not counted correctly | Verify SDEG field output is requested; check crack counting threshold |
| Peak stress too high vs. experiment | Cohesive elements too stiff before initiation | Ensure $K_n = 10^8$ MPa/mm, not higher |
| Memory error / too many elements | Model too fine | Use a coarser mesh; the paper uses a relatively coarse mesoscale mesh by design |
| `rho_sat` unknown | Not explicitly given in paper | Start with $\rho_{sat} = 1/t_{90}$ (standard saturation criterion) and calibrate to Fig. 11 |

---

## Appendix B: Missing Information & Reasonable Assumptions

The following parameters are NOT explicitly stated in the paper and must be assumed or calibrated:

| Parameter | Status | Recommended Assumption |
|-----------|--------|----------------------|
| Exact Vf range per thickness row | Not given | Interface rows: Uniform[0%, 30%]; Transition: Uniform[20%, 55%]; Center: Uniform[45%, 75%] |
| `rho_sat` value | Referenced to Hu et al. [17] | Start at $\rho_{sat} \approx 7{-}10$ cracks/mm for 255 µm ply; calibrate from Fig. 11a saturation |
| $G_{c,MT}$ fracture energy | Derived from unit cell curves (Fig. 8 of [29]) | Estimate as $G_{c,MT} \approx 0.1{-}0.3$ N/mm; calibrate from stiffness degradation slope |
| Characteristic element length $l_{char}$ | Implicit in ABAQUS | Use the element size in the thickness direction of the 90° ply |
| 0° ply material properties | Not given separately | Use Table 1 at 45% Vf; assume transverse isotropy |
| Number of Monte Carlo realizations | Not stated | Run at least 3–5 different random seeds to assess variability |

---

*Document generated for university project replication of UMCM-2025-1979.R1*
*Prepared by: Senior Research Engineer AI Assistant — May 2026*
