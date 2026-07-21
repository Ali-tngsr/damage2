# Damage2 — GUI Workflow Branch

Replication & extension of:
**Rumayshah et al. (ITB)** — *Unraveling Transverse Crack Multiplication in Thin-Ply Orthotropic Laminates: A Stochastic Finite Element Study* — Mechanics of Advanced Materials and Structures (UMCM-2025-1979.R1).

This branch implements the **GUI-based workflow**: build the model with `gui_build.py`, insert cohesive elements manually in Abaqus/CAE, then finalize with `gui_finish.py`.

---

## Repository Layout

```
.
├── README.md                       (this file)
├── WORKFLOW.md                     (step-by-step pipeline)
├── data/
│   ├── table1_properties.csv       (homogenized GF/PP props at 7 Vf levels)
│   ├── table1_transcribed.csv
│   └── experimental_fig5.csv       (digitized experimental data for Fig. 5)
└── scripts/
    ├── config.py                   (job registry, geometry, material constants)
    ├── mesoscale_common.py         (Table 1, Vf field, helpers)
    ├── material_interp.py          (linear interpolation on Table 1)
    ├── material_table.py           (parallel Table 1 source)
    ├── vf_field.py                 (stochastic Vf field generator)
    ├── add_vf_field.py             (add VF field to ODB for visualization)
    ├── build_mesoscale_model.py    (geometry + partitions + materials + mesh seeds)
    ├── Cohesive_Mat.py             (cohesive material/section + mesh)
    ├── Cohesive_Mat2.py            (crack-paths set)
    ├── OrphanMesh.py               (orphan mesh creation)
    ├── boundaryConditions.py       (assembly, BC, step, job)
    ├── run_pipeline.py             (single-job driver: build → resume → submit)
    ├── run_all.py                  (sanity-check: emit Table 1 CSV + Vf preview)
    ├── run_validation_sims.py      (3 validation jobs)
    ├── run_ply_number_study.py     (ply-number study jobs)
    ├── run_ply_thickness_study.py  (ply-thickness study jobs)
    ├── gui_build.py                (GUI: File → Run Script, builds model)
    ├── gui_finish.py               (GUI: File → Run Script, after manual cohesive)
    ├── postprocess_odb.py          (extract stress-strain, E90, crack density)
    ├── plot_figures.py             (Figs. 5, 9, 10, 11)
    ├── plot_figure_04.py           (Fig. 4 — mesoscale overview)
    ├── plot_figure_06.py           (Fig. 6 — crack morphology)
    ├── plot_results.py             (legacy plotter, kept for reference)
    ├── extract_crack_data.py       (crack morphology JSON for Figs. 6/7/8)
    ├── diagnose_odb.py             (ODB inspection utility)
    └── digitize_experimental.py    (template/check for experimental CSV)
```

## Quick Start

1. **One-time setup:**
   ```
   python scripts/run_all.py
   python scripts/digitize_experimental.py --template
   ```

2. **Build a single job (GUI workflow):**
   ```
   abaqus cae
   File → Run Script... → scripts/gui_build.py
   ```

3. **Insert cohesive elements manually** (see `WORKFLOW.md`).

4. **Finalize and submit (GUI):**
   ```
   File → Run Script... → scripts/gui_finish.py
   ```

5. **Post-process:**
   ```
   abaqus python scripts/postprocess_odb.py --odb abaqus_jobs/val_090s.odb
   python scripts/plot_figures.py --figures 5,9,10,11
   ```

See **WORKFLOW.md** for the full step-by-step pipeline.
