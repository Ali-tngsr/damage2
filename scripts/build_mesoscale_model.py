# -*- coding: utf-8 -*-
"""
Abaqus model builder for the thin-ply transverse-cracking study.

Run inside Abaqus:
    abaqus python build_mesoscale_model.py

Python 2.7 compatible.
"""

from __future__ import division

import os
import sys
import json
import math

try:
    import numpy as np
except ImportError:
    np = None

from material_table import interpolate_properties, to_engineering_constants_table
from vf_field import generate_vf_field, save_field_csv, print_field_summary
import config


def _ensure_dir(path):
    if not os.path.isdir(path):
        os.makedirs(path)


def _round_vf(vf):
    # Reduce duplicate material definitions while keeping physical variation.
    candidates = [0, 15, 30, 45, 60, 75, 90]
    return min(candidates, key=lambda x: abs(x - vf))


class ThinPlyModelBuilder(object):
    def __init__(self, model_name="ThinPlyModel", layup_key="SINGLE_90",
                 n_cols=config.DEFAULT_N_COLS, seed=config.DEFAULT_SEED,
                 out_dir="results"):
        self.model_name = model_name
        self.layup_key = layup_key
        self.n_cols = int(n_cols)
        self.seed = seed
        self.out_dir = out_dir
        self.layup = config.LAYUPS[layup_key]
        self.vf_field = None
        self.model = None
        self.mdb = None
        self.part_name = "LaminatePart"
        self.instance_name = "LaminateInst"
        self.element_map = {
            "PLY90": [],
            "COH": [],
        }

    def setup(self):
        _ensure_dir(self.out_dir)
        self.vf_field = generate_vf_field(self.n_cols, config.DEFAULT_N_ROWS, self.seed)
        save_field_csv(self.vf_field, os.path.join(self.out_dir, "vf_field.csv"))
        print_field_summary(self.vf_field)

    def import_abaqus(self):
        try:
            from abaqus import mdb
            import abaqusConstants as ac
            import mesh as mesh_module
        except Exception as exc:
            raise RuntimeError(
                "This script must run inside Abaqus/CAE or Abaqus Python. Import error: %s" % str(exc)
            )

        # Inject the constants used later in the script into module globals.
        constant_names = [
            "ENGINEERING_CONSTANTS", "TWO_D_PLANAR", "DEFORMABLE_BODY", "SIDE1",
            "QUAD", "STRUCTURED", "CPS4R", "STANDARD", "CARTESIAN", "ON",
            "UNSET", "ENERGY", "LINEAR", "DEFAULT", "TWO_D_PLANAR"
        ]
        g = globals()
        for name in constant_names:
            if hasattr(ac, name):
                g[name] = getattr(ac, name)

        # Mesh module is used when defining element types.
        g["mesh"] = mesh_module

        self.mdb = mdb
        self.abaqusConstants = ac

    def create_model(self):
        if self.mdb.models.has_key(self.model_name):
            del self.mdb.models[self.model_name]
        self.model = self.mdb.Model(name=self.model_name)

    def define_materials(self):
        # Create materials for rounded Vf bins only.
        used = {}
        for row in self.vf_field:
            for vf in row:
                used[_round_vf(vf)] = True

        for vf_bin in sorted(used.keys()):
            props = interpolate_properties(vf_bin)
            mat_name = "MAT_VF_%02d" % int(vf_bin)
            if mat_name in self.model.materials.keys():
                continue
            mat = self.model.Material(name=mat_name)
            mat.Elastic(type=ENGINEERING_CONSTANTS, table=(to_engineering_constants_table(vf_bin),))

        # Cohesive material template
        if "COH_TEMPLATE" not in self.model.materials.keys():
            coh = self.model.Material(name="COH_TEMPLATE")
            coh.Elastic(table=((config.PENALTY_STIFFNESS,
                                config.PENALTY_STIFFNESS,
                                config.PENALTY_STIFFNESS),))
            coh.MaxsDamageInitiation(table=((17.0, 8.5, 8.5),))
            coh.DamageEvolution(type=ENERGY, table=((1.0,),), softening=LINEAR)

    def build_geometry(self):
        """
        Starter geometry:
        A 2D rectangular mesoscale laminate block.
        The full paper uses a more detailed laminate with potential cohesive crack paths.
        This scaffold creates a structured part that can be partitioned later.
        """
        sketch = self.model.ConstrainedSketch(name="__profile__", sheetSize=500.0)
        sketch.rectangle(point1=(0.0, 0.0), point2=(config.GAUGE_LENGTH_MM, self.layup["total_thickness_mm"]))
        part = self.model.Part(name=self.part_name, dimensionality=TWO_D_PLANAR, type=DEFORMABLE_BODY)
        part.BaseShell(sketch=sketch)
        del sketch
        self.part = part

    def partition_cells(self):
        """
        Partition the 90-degree ply through thickness into 5 rows, and along length
        into n_cols columns. This is the structured basis required for the stochastic
        assignment and later crack-density extraction.
        """
        part = self.part
        t_total = self.layup["total_thickness_mm"]
        dy = t_total / float(config.DEFAULT_N_ROWS)
        dx = config.GAUGE_LENGTH_MM / float(self.n_cols)

        # Partition lines along x
        for i in range(1, self.n_cols):
            x = i * dx
            p1 = part.DatumPointByCoordinate(coords=(x, 0.0, 0.0))
            p2 = part.DatumPointByCoordinate(coords=(x, t_total, 0.0))
            line = part.MakeSketchTransform(sketchPlane=part.faces[0], sketchPlaneSide=SIDE1,
                                            sketchUpEdge=part.edges[0], origin=(0.0, 0.0, 0.0))
        # Partition lines along y
        # Abaqus partitioning APIs vary by release; this scaffold intentionally keeps
        # the geometry partitioning step explicit for adaptation to the target version.

    def assign_sections(self):
        """
        Assign a unique material section per Vf bin and a cohesive template section.
        """
        # The exact section assignment depends on the final partitioning strategy.
        # This scaffold prepares the materials; element set assignment is handled after meshing.
        pass

    def mesh_part(self):
        # Starter meshing settings.
        part = self.part
        part.seedPart(size=min(config.GAUGE_LENGTH_MM / 200.0, self.layup["total_thickness_mm"] / 20.0),
                      deviationFactor=0.1, minSizeFactor=0.1)
        part.setMeshControls(regions=part.faces, elemShape=QUAD, technique=STRUCTURED)
        elem_type = mesh.ElemType(elemCode=CPS4R, elemLibrary=STANDARD)
        part.setElementType(regions=(part.faces,), elemTypes=(elem_type,))
        part.generateMesh()

    def assemble(self):
        a = self.model.rootAssembly
        a.DatumCsysByDefault(CARTESIAN)
        inst = a.Instance(name=self.instance_name, part=self.part, dependent=ON)
        self.instance = inst

    def apply_bcs_and_step(self):
        model = self.model
        step = model.StaticStep(name="Step-1", previous="Initial", nlgeom=ON,
                                initialInc=1e-4, minInc=1e-9, maxInc=1e-2, maxNumInc=5000)

        a = model.rootAssembly
        inst = a.instances[self.instance_name]

        # Edge sets for boundary conditions.
        x0_faces = inst.edges.getByBoundingBox(xMin=-1e-6, xMax=1e-6,
                                               yMin=-1e-6, yMax=self.layup["total_thickness_mm"] + 1e-6,
                                               zMin=-1e-6, zMax=1e-6)
        x1_faces = inst.edges.getByBoundingBox(xMin=config.GAUGE_LENGTH_MM - 1e-6,
                                               xMax=config.GAUGE_LENGTH_MM + 1e-6,
                                               yMin=-1e-6, yMax=self.layup["total_thickness_mm"] + 1e-6,
                                               zMin=-1e-6, zMax=1e-6)

        if len(x0_faces) > 0:
            a.Set(name="SET_LEFT", edges=x0_faces)
            model.DisplacementBC(name="BC_LEFT", createStepName="Initial",
                                 region=a.sets["SET_LEFT"], u1=0.0, u2=UNSET, ur3=UNSET)
        if len(x1_faces) > 0:
            a.Set(name="SET_RIGHT", edges=x1_faces)
            model.DisplacementBC(name="BC_RIGHT", createStepName="Step-1",
                                 region=a.sets["SET_RIGHT"],
                                 u1=config.GAUGE_LENGTH_MM * config.MAX_ENGINEERING_STRAIN,
                                 u2=UNSET, ur3=UNSET, amplitude=UNSET)

        # Bottom edge roller.
        y0_edges = inst.edges.getByBoundingBox(xMin=-1e-6, xMax=config.GAUGE_LENGTH_MM + 1e-6,
                                                yMin=-1e-6, yMax=1e-6,
                                                zMin=-1e-6, zMax=1e-6)
        if len(y0_edges) > 0:
            a.Set(name="SET_BOTTOM", edges=y0_edges)
            model.DisplacementBC(name="BC_BOTTOM", createStepName="Initial",
                                 region=a.sets["SET_BOTTOM"], u2=0.0, u1=UNSET, ur3=UNSET)

    def create_job(self):
        job_name = "job_%s_%s" % (self.model_name, self.layup_key.lower())
        if job_name in self.mdb.jobs.keys():
            del self.mdb.jobs[job_name]
        self.mdb.Job(name=job_name, model=self.model_name,
                     numCpus=4, numDomains=4, multiprocessingMode=DEFAULT)
        return job_name

    def write_summary(self):
        summary = {
            "model_name": self.model_name,
            "layup_key": self.layup_key,
            "n_cols": self.n_cols,
            "seed": self.seed,
            "gauge_length_mm": config.GAUGE_LENGTH_MM,
            "total_thickness_mm": self.layup["total_thickness_mm"],
            "max_strain": config.MAX_ENGINEERING_STRAIN,
            "vf_field_csv": os.path.join(self.out_dir, "vf_field.csv"),
        }
        path = os.path.join(self.out_dir, "model_summary.json")
        f = open(path, "w")
        try:
            json.dump(summary, f, indent=2, sort_keys=True)
        finally:
            f.close()
        return path

    def run(self):
        self.setup()
        self.import_abaqus()
        self.create_model()
        self.define_materials()
        self.build_geometry()
        self.partition_cells()
        self.assign_sections()
        self.mesh_part()
        self.assemble()
        self.apply_bcs_and_step()
        job_name = self.create_job()
        self.write_summary()
        print("Built job: %s" % job_name)
        return job_name


def main():
    layup_key = "SINGLE_90"
    if len(sys.argv) > 1:
        layup_key = sys.argv[1]
    builder = ThinPlyModelBuilder(layup_key=layup_key)
    builder.run()


if __name__ == "__main__":
    main()
