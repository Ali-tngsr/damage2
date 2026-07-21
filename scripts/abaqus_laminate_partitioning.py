# -*- coding: utf-8 -*-
"""
=============================================================================
ABAQUS Python Script - Stochastic Mesoscale Laminate Partitioning (2D)
=============================================================================
Article: "Unraveling Transverse Crack Multiplication in Thin-Ply Orthotropic
          Laminates: A Stochastic Finite Element Study"
Journal: Mechanics of Advanced Materials and Structures (2025)

This script uses the SAME proven approach as build_mesoscale_model.py:
  - PartitionFaceBySketch (NOT DatumPlane) for partitioning
  - getByBoundingBox for set creation
  - findAt for individual cell selection (legacy; preserved as-is per user request)
  - Engineering constants with 90 deg swap for fiber along axis-3 in 2D

Stages covered:
  Stage 0: 2D base geometry
  Stage 1-3: Horizontal + vertical partitioning with sketch
  Stage 4: Face sets (Ply_0_Set, Set_90deg_Vf_*.*, Potential_Crack_Edges)
  Stage 5: Materials + Sections + Section assignments  <-- NEW
  Stage 6: MaterialOrientation (GLOBAL, AXIS_3)         <-- NEW

Compatibility: ABAQUS Python 2.7
  - NO f-strings (uses .format() and % formatting)
  - NO Python 3-only features
=============================================================================
"""

from abaqus import *
from abaqusConstants import *
import part
import mesh
import regionToolset
import logging
import random

# ============================================================
# Defensive builtins — Abaqus گاهی sum/min/max را shadow می‌کند
# ============================================================
# نکته مهم: `from abaqus import *` و `from abaqusConstants import *`
# ممکن است برخی توابع built-in پایتون (به‌خصوص `sum`) را با توابع
# داخلی Abaqus جایگزین کنند. این توابع Abaqus generator expression ها
# را قبول نمی‌کنند و خطای "arg1; found 'generator', expecting a
# recognized type" می‌دهند.
#
# راه‌حل: استفاده صریح از __builtin__.sum که همیشه پایتونی واقعی است.
try:
    import __builtin__ as _bi  # Python 2.7 (Abaqus)
except ImportError:
    import builtins as _bi     # Python 3
_py_sum = _bi.sum
_py_min = _bi.min
_py_max = _bi.max
_py_len = _bi.len

# ============================================================
# USER INPUTS - ویرایش این مقادیر
# ============================================================

# --- ورودی‌های هندسی (Geometry inputs) - 2D ---
# مقادیر "Paper" دقیقاً از §2.2 مقاله گرفته شده‌اند:
#   L_paper = 80 mm (gauge 70 mm + 5 mm buffer هر طرف)
#   L_gauge_paper = 70 mm
#
# اگه سیستم قوی نیست، می‌تونی با SCALE_FACTOR مدل رو کوچیک کنی:
#   SCALE_FACTOR = 1.0  → مقادیر مقاله (L=80, L_gauge=70, rho=8)  → ~1-2 hr/job
#   SCALE_FACTOR = 0.5  → نصف (L=40, L_gauge=35, rho=4)             → ~20-30 min/job
#   SCALE_FACTOR = 0.25 → یک‌چهارم (L=20, L_gauge=15, rho=2)        → ~5-10 min/job
#   SCALE_FACTOR = 0.125 → یک‌هشتم (L=10, L_gauge=5, rho=1)         → ~2-3 min/job
#
# نکته: rho هم scale می‌شه تا تعداد ترک‌ها متناسب با طول بمونه. این یعنی
# crack spacing ثابت می‌مونه و مقایسه با مقاله معناداره.
SCALE_FACTOR = 0.25           # ← این رو تغییر بده (1.0 = مقادیر مقاله)

# مقادیر پایه از مقاله
L_PAPER = 80.0
L_GAUGE_PAPER = 70.0
RHO_PAPER = 8.0               # در JOB_PROFILES با این override می‌شه

# اعمال scale factor
L = L_PAPER * SCALE_FACTOR                # طول نمونه [mm]
L_gauge = L_GAUGE_PAPER * SCALE_FACTOR    # طول gauge [mm]

# --- ورودی‌های لایه (Ply inputs) ---
t0 = 0.250          # ضخامت هر لایه 0° [mm]
t90 = 0.250         # ضخامت هر لایه 90° [mm]
n90 = 1             # تعداد لایه‌های 90°

# --- نوع لایه‌چینی (Layup type) ---
# 'symmetric'  => [0/90n]s = 0 / 90*n / 90*n / 0
# 'asymmetric' => [0/90/0] = 0 / 90*n90 / 0
layup_type = 'symmetric'

# --- نوع تحلیل 2D (2D analysis type) ---
# 'PLANE_STRAIN'  => CPE4R elements
# 'PLANE_STRESS'  => CPS4R elements
analysis_type = 'PLANE_STRAIN'

# --- پارامترهای Stochastic ---
n_cells_thickness = 5    # تعداد زیرسلول‌های هر لایه 90° در ضخامت
rho = 0.5                # چگالی اشباع ترک [cracks/mm]

# --- تنظیمات مدل ---
model_name = 'Laminate_Model'
part_name = 'Laminate'
# نکته: Orphan mesh حذف شد — برای مدل ما لازم نیست.
# ابزار 'Insert cohesive seams' روی هندسه کار می‌کند و Instance مستقیماً
# از part اصلی ساخته می‌شود.

# --- تنظیمات Mesh ---
# اندازه المان [mm] برای mesh generation.
# نکته مهم: این مقدار در apply_job_profile() به‌صورت خودکار به dy = t90/n_cells
# تنظیم می‌شه تا mesh با partitions هم‌راستا بشه و المان‌ها مربعی بمونن.
# اگه می‌خوای مقدار ثابتی داشته باشه، APPLY_AUTO_MESH_SIZE = False کن.
APPLY_AUTO_MESH_SIZE = True
mesh_element_size = 0.05    # مقدار پیش‌فرض (در صورت غیرفعال بودن auto)

# --- سیاست انتخاب مسیرهای ترک ---
# سلول‌های continuum همیشه مربعی هستن: dx = dy = t90/n_cells_thickness
# ولی مسیرهای ترک (cohesive paths) با spacing متفاوت انتخاب می‌شن.
#
# دو روش برای انتخاب crack spacing:
#   RHO_BASED  (پیش‌فرض): n_cracks = rho * L
#                          → تعداد ترک‌ها بر اساس چگالی ترک مقاله
#   FIXED_SPACING: cracks هر CRACK_SPACING mm یکبار قرار می‌گیرن
#                          → تعداد ترک‌ها = L / CRACK_SPACING
#
# مثال (با L=20mm):
#   RHO_BASED با rho=2.0:     n_cracks = 2.0 * 20 = 40 → crack_spacing = 0.5mm
#   FIXED_SPACING با 0.5mm:   n_cracks = 20 / 0.5 = 40 (همون نتیجه)
CRACK_SELECTION_MODE = 'RHO_BASED'   # یا 'FIXED_SPACING'
CRACK_SPACING_MM = 0.5               # فقط وقتی CRACK_SELECTION_MODE = 'FIXED_SPACING'

# --- تنظیمات Cohesive ---
cohesive_material_name = 'Cohesive_Mat'
cohesive_section_name = 'Cohesive_Sec'
cohesive_strength = 17.0          # MPa (میانگین YT از Table 1 در Vf=45%)
cohesive_fracture_energy = 0.2    # N/mm (G_c از مقاله — نیازمند کالیبراسیون)
cohesive_penalty_stiffness = 1.0e8  # MPa/mm (K_n = K_s = K_t)
cohesive_viscosity = 1.0e-4       # Element Controls viscosity (Section Controls)
cohesive_initial_thickness = 0.001  # mm (Initial thickness: Specify, عدد کوچک)

# --- تنظیمات Analysis ---
applied_strain = 0.025            # 2.5% کرنش کششی
job_name = 'Tensile_Test_Stochastic'
job_cpus = 4
job_domains = 4

# --- Mode Control ---
# 'build'  : اجرای کامل از ابتدا (geometry + partition + sets + materials + mesh)
# 'resume' : اجرای نهایی بعد از درج دستی cohesive (assembly + BC + step + job)
run_mode = 'build'
auto_submit_job = False           # آیا job بعد از ساخت خودکار submit شود؟


# ============================================================
# JOB PROFILES - ۸ تحلیل برای بازتولید مقاله
# ============================================================
# برای اجرای هر تحلیل، فقط ACTIVE_JOB رو به نام دلخواه تغییر بده.
# پارامترهای هندسی، layup، ضخامت و job_name از این پروفایل لود می‌شن.
#
# ۸ job تعریف‌شده (مطابق config.py مقاله):
#   - val_090s   : [0/90]s   (validation)            → Figs 5, 6, 9, 11a
#   - val_0902s  : [0/902]s  (validation)            → Figs 5, 6, 9, 11a
#   - val_0904s  : [0/904]s  (validation)            → Figs 5, 6, 8
#   - pn_090n0   : [0/90/0]  (ply number study)      → Figs 9, 11a
#   - pt_t90_020 : [0/90/0]  (ply thickness, t90=20 µm)  → Figs 10, 11b
#   - pt_t90_060 : [0/90/0]  (ply thickness, t90=60 µm)  → Figs 10, 11b
#   - pt_t90_100 : [0/90/0]  (ply thickness, t90=100 µm) → Figs 10, 11b
#   - pt_t90_140 : [0/90/0]  (ply thickness, t90=140 µm) → Figs 10, 11b
# ============================================================

JOB_PROFILES = {
    # --- Validation sims (Phase B) → Figures 5, 6 ---
    'val_090s': {
        'layup_type': 'symmetric',
        'n90': 1,                # [0/90]s = [0/90/90/0]
        't0': 0.250,
        't90': 0.255,            # 255 µm — elementary ply
        'rho': 8.0,              # cracks/mm (DEFAULT_RHO_SAT)
        'purpose': 'Figs 5, 6, 9, 11a',
    },
    'val_0902s': {
        'layup_type': 'symmetric',
        'n90': 2,                # [0/902]s = [0/90/90/90/90/0]
        't0': 0.250,
        't90': 0.255,            # per-ply thickness (modeling as block equivalent)
        'rho': 8.0,
        'purpose': 'Figs 5, 6, 9, 11a',
    },
    'val_0904s': {
        'layup_type': 'symmetric',
        'n90': 4,                # [0/904]s
        't0': 0.250,
        't90': 0.255,
        'rho': 8.0,
        'purpose': 'Figs 5, 6, 8',
    },

    # --- Ply number study (Phase C) → Figures 9, 11a ---
    'pn_090n0': {
        'layup_type': 'asymmetric',
        'n90': 1,                # [0/90/0] — single 90° ply, non-symmetric
        't0': 0.250,
        't90': 0.255,
        'rho': 8.0,
        'purpose': 'Figs 9, 11a',
    },

    # --- Ply thickness study (Phase D) → Figures 10, 11b ---
    'pt_t90_020': {
        'layup_type': 'asymmetric',
        'n90': 1,                # [0/90/0]
        't0': 0.250,
        't90': 0.020,            # 20 µm — thin-ply
        'rho': 8.0,
        'purpose': 'Figs 10, 11b',
    },
    'pt_t90_060': {
        'layup_type': 'asymmetric',
        'n90': 1,
        't0': 0.250,
        't90': 0.060,            # 60 µm
        'rho': 8.0,
        'purpose': 'Figs 10, 11b',
    },
    'pt_t90_100': {
        'layup_type': 'asymmetric',
        'n90': 1,
        't0': 0.250,
        't90': 0.100,            # 100 µm
        'rho': 8.0,
        'purpose': 'Figs 10, 11b',
    },
    'pt_t90_140': {
        'layup_type': 'asymmetric',
        'n90': 1,
        't0': 0.250,
        't90': 0.140,            # 140 µm
        'rho': 8.0,
        'purpose': 'Figs 10, 11b',
    },
}

# ====== پروفایل فعال — فقط این خط رو تغییر بده ======
#   ACTIVE_JOB = 'val_090s'
# ====================================================
# برای اجرای job دیگه، نامش رو اینجا بذار:
#   ACTIVE_JOB = 'val_090s'
#   ACTIVE_JOB = 'val_0902s'
#   ACTIVE_JOB = 'val_0904s'
#   ACTIVE_JOB = 'pn_090n0'
ACTIVE_JOB = 'pt_t90_020'
#   ACTIVE_JOB = 'pt_t90_060'
#   ACTIVE_JOB = 'pt_t90_100'
#   ACTIVE_JOB = 'pt_t90_140'
# ====================================================


def apply_job_profile():
    """
    اعمال پارامترهای ACTIVE_JOB روی متغیرهای سراسری.

    این تابع در ابتدای main() فراخوانی می‌شه و پارامترهای layup_type,
    n90, t0, t90, rho, job_name رو از پروفایل فعال override می‌کنه.
    """
    global layup_type, n90, t0, t90, rho, job_name

    if ACTIVE_JOB not in JOB_PROFILES:
        print("[ERROR] ACTIVE_JOB '{}' not found in JOB_PROFILES!".format(ACTIVE_JOB))
        print("[INFO] Available jobs: {}".format(', '.join(sorted(JOB_PROFILES.keys()))))
        return False

    profile = JOB_PROFILES[ACTIVE_JOB]

    # Override متغیرهای سراسری
    layup_type = profile['layup_type']
    n90 = profile['n90']
    t0 = profile['t0']
    t90 = profile['t90']
    # rho با SCALE_FACTOR scale می‌شه تا crack spacing ثابت بمونه
    # این یعنی تعداد ترک‌ها متناسب با طول نمونه کم/زیاد می‌شه
    #rho = profile['rho'] * SCALE_FACTOR
    rho = profile['rho']
    job_name = ACTIVE_JOB  # نام job = نام profile
    # model_name و part_name هم برای هر job جداگانه می‌شن
    # (با global declaration)
    globals()['model_name'] = 'Model_{}'.format(ACTIVE_JOB)
    globals()['part_name'] = 'Laminate_{}'.format(ACTIVE_JOB)

    # محاسبه اندازه مدل برای اطلاع‌رسانی
    dy = t90 / float(n_cells_thickness)
    dx = dy  # همیشه مربعی
    n_cols = int(L / dx)
    n_90_plies = 2 * n90 if layup_type == 'symmetric' else n90
    t90_total = t90 * n_90_plies

    # تعداد ترک‌ها بر اساس CRACK_SELECTION_MODE
    if CRACK_SELECTION_MODE == 'FIXED_SPACING':
        n_cracks = max(1, int(round(L / CRACK_SPACING_MM)))
        crack_spacing = CRACK_SPACING_MM
    else:  # RHO_BASED (پیش‌فرض)
        n_cracks = max(1, int(round(rho * L)))
        crack_spacing = L / n_cracks if n_cracks > 0 else 0.0

    expected_cohesive = n_cracks * n_90_plies * n_cells_thickness
    expected_continuum = n_cols * (n_90_plies * n_cells_thickness + 2)  # تقریبی

    # تنظیم خودکار mesh_element_size به dy برای هم‌راستایی با partitions
    if APPLY_AUTO_MESH_SIZE:
        globals()['mesh_element_size'] = dy

    print("")
    print("=" * 70)
    print("ACTIVE JOB PROFILE: {}".format(ACTIVE_JOB))
    print("=" * 70)
    print("  SCALE_FACTOR: {}  (1.0 = paper values)".format(SCALE_FACTOR))
    print("  Layup type:   {}".format(layup_type))
    print("  n90:          {}".format(n90))
    print("  t0:           {} mm".format(t0))
    print("  t90:          {} mm".format(t90))
    print("  rho:          {} cracks/mm  (scaled from {})".format(rho, profile['rho']))
    print("  L:            {} mm  (scaled from {})".format(L, L_PAPER))
    print("  L_gauge:      {} mm  (scaled from {})".format(L_gauge, L_GAUGE_PAPER))
    print("  job_name:     {}".format(job_name))
    print("  model_name:   {}".format(globals()['model_name']))
    print("  part_name:    {}".format(globals()['part_name']))
    print("  Purpose:      {}".format(profile.get('purpose', 'N/A')))
    print("")
    print("  Cell geometry (SQUARE cells):")
    print("    dy = t90/n_cells:          {:.6f} mm".format(dy))
    print("    dx = dy (square):          {:.6f} mm".format(dx))
    print("    mesh_element_size:         {:.6f} mm".format(globals().get('mesh_element_size', 0)))
    print("    n_cols (along length):     {}".format(n_cols))
    print("")
    print("  Crack selection:")
    print("    Mode:                      {}".format(CRACK_SELECTION_MODE))
    print("    n_cracks:                  {}".format(n_cracks))
    print("    crack_spacing:             {:.4f} mm".format(crack_spacing))
    print("    n_cracks per partition:    1 / {:.1f}".format(n_cols / max(1, n_cracks)))
    print("")
    print("  Estimated model size:")
    print("    Cohesive elements:         ~{}".format(expected_cohesive))
    print("    Continuum elements:        ~{}".format(expected_continuum))
    print("    Total elements:            ~{}".format(expected_cohesive + expected_continuum))
    print("=" * 70)
    return True


# ============================================================
# تنظیمات توزیع کسر حجمی (درصدی) و تعداد ست‌ها
# ============================================================
TARGET_VF = 45.0           # میانگین درصدی الیاف که باید به دست بیاید
NUM_MATERIAL_SETS = 10     # تعداد ست‌های متریال مورد نیاز (تولید بازه‌های مساوی بین 0 تا 90)
                           # این پارامتر داینامیک است: می‌توانید آن را به 7، 20، 50، یا هر
                           # مقدار دیگری تغییر دهید و خواص متریال در زمان اجرا با
                           # interpolation خطی روی Table 1 محاسبه می‌شوند.


def generate_vf_levels(num_sets, target_vf=45.0):
    """
    تولید لیست سطوح Vf به صورت داینامیک در زمان اجرا.

    الگو:
      - num_sets == 7  =>  استفاده از نقاط دقیق Table 1 (0, 15, 30, 45, 60, 75, 90)
                           که هیچ interpolation لازم ندارند.
      - num_sets > 1   =>  بازه‌های مساوی بین 0 تا 90 (شامل هر دو سر)
                           مثلاً num_sets=10 => [0, 10, 20, 30, 40, 50, 60, 70, 80, 90]
                           مثلاً num_sets=20 => [0, 4.74, 9.47, ..., 90]
      - num_sets == 1  =>  فقط target_vf (یک متریال یکنواخت)

    پارامترها:
      num_sets   : تعداد سطوح Vf (integer >= 1)
      target_vf  : Vf هدف برای حالت num_sets=1

    خروجی:
      لیست float ها با طول num_sets (همگی در بازه [0, 90])
    """
    table1_vfs = [0.0, 15.0, 30.0, 45.0, 60.0, 75.0, 90.0]

    if num_sets == 7:
        # حالت خاص: استفاده از نقاط دقیق Table 1 (بدون نیاز به interpolation)
        return list(table1_vfs)

    if num_sets == 1:
        return [float(target_vf)]

    if num_sets < 1:
        raise ValueError("num_sets must be >= 1, got {}".format(num_sets))

    # بازه مساوی بین 0 تا 90 با num_sets نقطه (شامل هر دو سر)
    levels = []
    step = 90.0 / float(num_sets - 1)
    for i in range(num_sets):
        vf = i * step
        # گردسازی به ۴ رقم اعشار برای جلوگیری از خطای float
        vf = round(vf, 4)
        # clamping ایمنی
        if vf < 0.0:
            vf = 0.0
        elif vf > 90.0:
            vf = 90.0
        levels.append(vf)
    return levels


# تولید VF_LEVELS در زمان اجرا (در سطح ماژول، با مقدار NUM_MATERIAL_SETS فعلی)
VF_LEVELS = generate_vf_levels(NUM_MATERIAL_SETS, TARGET_VF)


# ============================================================
# TABLE 1 - خواص homogenized کامپوزیت GF/PP از مقاله
# منبع: data/table1_properties.csv در repo مقاله
# واحدها: E و G به GPa، YT به MPa
#
# نکته مهم: این ۷ نقطه فقط "نقاط گرهی" interpolation هستند.
# هر Vf دیگری در بازه [0, 90] (مثلاً 22.5 یا 47.3) با interpolation
# خطی در زمان اجرا محاسبه می‌شود. به این ترتیب می‌توان NUM_MATERIAL_SETS
# را به هر مقداری (7، 10، 20، 50، ...) تغییر داد بدون نیاز به تغییر این جدول.
# ============================================================
TABLE1_ROWS = (
    {'Vf': 0.0,  'E11': 1.70,  'nu12': 0.40, 'E22': 1.70,  'nu23': 0.40, 'YT': 20.0, 'G12': 0.61, 'G23': 0.61},
    {'Vf': 15.0, 'E11': 12.20, 'nu12': 0.64, 'E22': 2.48,  'nu23': 0.34, 'YT': 19.0, 'G12': 0.81, 'G23': 0.78},
    {'Vf': 30.0, 'E11': 22.73, 'nu12': 0.59, 'E22': 3.25,  'nu23': 0.34, 'YT': 18.0, 'G12': 1.09, 'G23': 1.02},
    {'Vf': 45.0, 'E11': 33.29, 'nu12': 0.54, 'E22': 4.45,  'nu23': 0.32, 'YT': 17.0, 'G12': 1.51, 'G23': 1.43},
    {'Vf': 60.0, 'E11': 43.80, 'nu12': 0.49, 'E22': 6.59,  'nu23': 0.28, 'YT': 16.0, 'G12': 2.21, 'G23': 2.21},
    {'Vf': 75.0, 'E11': 54.31, 'nu12': 0.45, 'E22': 10.89, 'nu23': 0.23, 'YT': 15.0, 'G12': 3.68, 'G23': 3.90},
    {'Vf': 90.0, 'E11': 64.85, 'nu12': 0.40, 'E22': 17.98, 'nu23': 0.16, 'YT': 14.0, 'G12': 6.15, 'G23': 6.80},
)
PROPERTY_NAMES = ('E11', 'nu12', 'E22', 'nu23', 'YT', 'G12', 'G23')
MODULUS_NAMES = ('E11', 'E22', 'G12', 'G23')  # این‌ها برای تبدیل GPa->MPa ضرب در 1000 می‌شن


def _linear_interp(x_value, x_data, y_data):
    """
    Piecewise linear interpolation with end-value clamping.

    اگر x_value خارج از بازه [x_data[0], x_data[-1]] باشد، به نزدیک‌ترین
    مقدار انتهایی clamp می‌شود (نه extrapolation). این رفتار فیزیک پایدار است:
      - Vf < 0  =>  خواص Vf=0  (pure matrix)
      - Vf > 90 =>  خواص Vf=90 (pure fiber)
    """
    x_value = float(x_value)
    if x_value <= x_data[0]:
        return float(y_data[0])
    if x_value >= x_data[-1]:
        return float(y_data[-1])
    for idx in range(1, len(x_data)):
        x0 = x_data[idx - 1]
        x1 = x_data[idx]
        if x_value <= x1:
            y0 = y_data[idx - 1]
            y1 = y_data[idx]
            ratio = (x_value - x0) / (x1 - x0)
            return float(y0 + ratio * (y1 - y0))
    return float(y_data[-1])


def get_properties(vf_target, units='MPa'):
    """
    محاسبهٔ خواص متریال برای هر Vf دلخواه در زمان اجرا.

    این تابع قلب interpolation داینامیک است:
      - اگر vf_target دقیقاً یکی از نقاط Table 1 باشد (0, 15, 30, 45, 60, 75, 90)
        => مقدار دقیق جدول برگردانده می‌شود.
      - در غیر این صورت => interpolation خطی بین دو نقطهٔ مجاور Table 1.
      - Vf خارج از [0, 90] => clamp به نزدیک‌ترین سر.

    Parameters
    ----------
    vf_target : float
        Fiber volume fraction در درصد. هر مقداری در [0, 90] مجاز است.
    units : str
        'GPa' : واحدهای Table 1 (E و G به GPa، YT به MPa)
        'MPa' : تبدیل به mm-MPa (E و G × 1000) — مناسب Abaqus model

    Returns
    -------
    dict with keys: Vf, E11, nu12, E22, nu23, YT, G12, G23
    """
    vf_data = [row['Vf'] for row in TABLE1_ROWS]
    props = {}
    for name in PROPERTY_NAMES:
        data = [row[name] for row in TABLE1_ROWS]
        value = _linear_interp(vf_target, vf_data, data)
        if units == 'MPa' and name in MODULUS_NAMES:
            value *= 1000.0
        props[name] = value
    # Vf clamped (برای گزارش/دیباگ)
    props['Vf'] = max(vf_data[0], min(float(vf_target), vf_data[-1]))
    return props


def print_interpolation_table(vf_levels, units='MPa'):
    """
    چاپ جدول خواص محاسبه‌شده برای همهٔ VF_LEVELS در زمان اجرا.

    این تابع برای شفافیت و دیباگ استفاده می‌شود تا کاربر ببیند برای هر
    سطح Vf، چه خواصی به‌صورت داینامیک محاسبه شده‌اند.
    """
    print("")
    print("=" * 100)
    print("DYNAMIC INTERPOLATION TABLE - Properties computed at runtime")
    print("Source: Table 1 (7 anchor points) -> Linear interpolation")
    print("Units: {} | Target mean Vf: {:.2f}% | NUM_MATERIAL_SETS: {}".format(
        units, TARGET_VF, len(vf_levels)))
    print("=" * 100)
    header = "  {:>6} | {:>12} | {:>12} | {:>7} | {:>7} | {:>12} | {:>12} | {:>9} | {:>8}".format(
        'Vf', 'E11', 'E22', 'nu12', 'nu23', 'G12', 'G23', 'YT', 'nu21')
    if units == 'MPa':
        header = header.replace('E11', 'E11(MPa)').replace('E22', 'E22(MPa)')
        header = header.replace('G12', 'G12(MPa)').replace('G23', 'G23(MPa)')
        header = header.replace('YT', 'YT(MPa)')
    else:
        header = header.replace('E11', 'E11(GPa)').replace('E22', 'E22(GPa)')
        header = header.replace('G12', 'G12(GPa)').replace('G23', 'G23(GPa)')
        header = header.replace('YT', 'YT(MPa)')
    print(header)
    print("  " + "-" * 96)

    for vf in vf_levels:
        p = get_properties(vf, units=units)
        nu21 = p['nu12'] * p['E22'] / p['E11']
        print("  {:6.2f} | {:12.2f} | {:12.2f} | {:7.4f} | {:7.4f} | {:12.2f} | {:12.2f} | {:9.2f} | {:8.4f}".format(
            vf, p['E11'], p['E22'], p['nu12'], p['nu23'],
            p['G12'], p['G23'], p['YT'], nu21))

    # علامت‌گذاری نقاط دقیق Table 1
    table1_vfs = set([0.0, 15.0, 30.0, 45.0, 60.0, 75.0, 90.0])
    # نکته: از _py_sum استفاده می‌کنیم چون `sum` ممکن است توسط Abaqus shadow شده باشد
    # و generator expression ها را قبول نمی‌کند (خطای arg1; found 'generator').
    exact_count = _py_sum(1 for v in vf_levels if v in table1_vfs)
    interp_count = len(vf_levels) - exact_count
    print("  " + "-" * 96)
    print("  Exact Table 1 points: {} | Interpolated points: {}".format(
        exact_count, interp_count))
    print("=" * 100)


# ============================================================
# COMPUTE LAYUP SEQUENCE
# ============================================================

def build_layup(layup_type, n90, t0, t90):
    """ساخت دنباله لایه‌چینی از پایین به بالا."""
    layup = []
    if layup_type == 'symmetric':
        layup.append((0, t0))
        for i in range(n90):
            layup.append((90, t90))
        for i in range(n90):
            layup.append((90, t90))
        layup.append((0, t0))
    elif layup_type == 'asymmetric':
        layup.append((0, t0))
        for i in range(n90):
            layup.append((90, t90))
        layup.append((0, t0))
    else:
        raise ValueError("layup_type must be 'symmetric' or 'asymmetric'")
    return layup


def print_layup_info(layup, t0, t90, n90, layup_type):
    """نمایش اطلاعات لایه‌چینی."""
    print("")
    print("=" * 70)
    print("LAYUP INFORMATION - 2D Cross-section Analysis")
    print("=" * 70)
    print("Layup type: {}".format(layup_type))
    print("Analysis type: {}".format(analysis_type))
    print("Number of 90 plies (input n90): {}".format(n90))

    if layup_type == 'symmetric':
        n90_total = 2 * n90
        if n90 > 1:
            symbol = "[0/90{}]s".format(n90)
        else:
            symbol = "[0/90]s"
    else:
        n90_total = n90
        if n90 > 1:
            symbol = "[0/90{}/0]".format(n90)
        else:
            symbol = "[0/90/0]"
    print("Layup symbol: {}".format(symbol))
    print("Total 90 plies: {}".format(n90_total))
    print("Total 0 plies: 2")
    print("")
    print("Layup sequence (bottom to top):")
    print("-" * 50)
    for i in range(len(layup)):
        angle = layup[i][0]
        t = layup[i][1]
        if angle == 0:
            direction = " longitudinal (fiber dir.)"
        else:
            direction = " transverse"
        print("  Ply {:2d}: {:3d} deg | t = {:.3f} mm |{}".format(i+1, angle, t, direction))
    print("-" * 50)
    total_t = 0.0
    for item in layup:
        total_t += item[1]
    print("Total thickness: {:.3f} mm".format(total_t))
    print("Specimen length: {:.3f} mm".format(L))
    print("Gauge length: {:.3f} mm".format(L_gauge))
    print("=" * 70)
    print("")


# ============================================================
# CREATE 2D BASE GEOMETRY - ساخت هندسه پایه 2D
# ============================================================

def create_base_geometry_2d(model_name, part_name, L, total_thickness):
    """ساخت پارت پایه به صورت 2D planar (سطح مقطع)."""
    # اگر مدل وجود دارد، حذف کن
    model_keys = mdb.models.keys()
    if model_name in model_keys:
        del mdb.models[model_name]
    mdb.Model(model_name)

    # ساخت اسکچ پروفایل (مستطیل در صفحه X-Y)
    sketch = mdb.models[model_name].ConstrainedSketch(
        name='profile',
        sheetSize=200.0)
    sketch.rectangle(point1=(0.0, 0.0), point2=(L, total_thickness))

    # ساخت پارت 2D planar
    p = mdb.models[model_name].Part(
        name=part_name,
        dimensionality=TWO_D_PLANAR,
        type=DEFORMABLE_BODY)
    p.BaseShell(sketch=sketch)

    print("[OK] Created 2D part '{}': L={} mm x t={:.4f} mm".format(
        part_name, L, total_thickness))
    return p


# ============================================================
# PARTITION USING SKETCH (proven method from build_mesoscale_model.py)
# ============================================================

def partition_with_sketch(p, model, L, total_thickness, layup, n_cells_thickness,
                          L_gauge, rho):
    print("")
    print("--- Partitioning with Sketch method (Square Elements, Entire Model) ---")

    ply_y_boundaries = []
    y_ranges_90 = []
    y_start = 0.0

    for i in range(len(layup)):
        angle = layup[i][0]
        t = layup[i][1]
        y_end = y_start + t
        if i < len(layup) - 1:
            ply_y_boundaries.append(y_end)
        if angle == 90:
            y_ranges_90.append((y_start, y_end))
        y_start = y_end

    subcell_y = []
    y_start = 0.0
    t90_sample = 0.0
    for item in layup:
        angle = item[0]
        t = item[1]
        y_end = y_start + t
        if angle == 90:
            t90_sample = t
            dy = t / float(n_cells_thickness)
            for j in range(1, n_cells_thickness):
                subcell_y.append(y_start + j * dy)
        y_start = y_end

    dy = t90_sample / float(n_cells_thickness)
    # dx همیشه برابر dy هست تا سلول‌های continuum مربعی بمونن
    # (طبق درخواست: "dx همیشه باید مربعی و یک‌اندازه هر لایه ۹۰ درجه باشه")
    dx = dy

    # رسم خطوط عمودی برای **کل طول مدل** (از 0 تا L)
    cohesive_x = []
    current_x = 0.0
    while True:
        current_x += dx
        if current_x >= L - 1e-5:
            break
        cohesive_x.append(current_x)

    n_cohesive = len(cohesive_x)

    # مرحله 1: پارتیشن‌های افقی
    print("  Creating horizontal sketch...")
    horiz_sketch = model.ConstrainedSketch(name='partition_horizontal', sheetSize=200.0)
    for y in ply_y_boundaries:
        horiz_sketch.Line(point1=(0.0, y), point2=(L, y))
    for y in subcell_y:
        horiz_sketch.Line(point1=(0.0, y), point2=(L, y))
    p.PartitionFaceBySketch(faces=p.faces, sketch=horiz_sketch)

    # مرحله 2: پارتیشن‌های عمودی (فقط در لایه‌های 90 درجه)
    print("  Creating vertical sketch (restricted to 90 deg plies)...")
    vert_sketch = model.ConstrainedSketch(name='partition_vertical', sheetSize=200.0)

    for x in cohesive_x:
        vert_sketch.Line(point1=(x, -total_thickness), point2=(x, 2.0 * total_thickness))

    tol = 1e-4
    for y_min, y_max in y_ranges_90:
        faces_to_cut = p.faces.getByBoundingBox(
            xMin=-tol, yMin=y_min - tol, zMin=-tol,
            xMax=L + tol, yMax=y_max + tol, zMax=tol)

        if len(faces_to_cut) > 0:
            p.PartitionFaceBySketch(faces=faces_to_cut, sketch=vert_sketch)

    print("  [OK] Vertical partitions applied to the entire length successfully")

    return n_cohesive


# ============================================================
# CREATE FACE SETS - استفاده از findAt و getByBoundingBox
# ============================================================

def create_face_sets(p, layup, L, n_cells_thickness):
    print("")
    print("--- Stage 4: Creating face sets (Dynamic Stochastic Vf) ---")

    y_min_0, y_max_0 = 1e10, -1e10
    y_min_90, y_max_90 = 1e10, -1e10

    y_start = 0.0
    for item in layup:
        angle = item[0]
        t = item[1]
        y_end = y_start + t
        if angle == 0:
            y_min_0 = min(y_min_0, y_start)
            y_max_0 = max(y_max_0, y_end)
        else:
            y_min_90 = min(y_min_90, y_start)
            y_max_90 = max(y_max_90, y_end)
        y_start = y_end

    tol = 1e-4

    faces_0 = []

    y_start = 0.0

    for angle, t in layup:

        y_end = y_start + t

        if angle == 0:

            y_mid = 0.5 * (y_start + y_end)

            try:
                f = p.faces.findAt(((L * 0.5, y_mid, 0.0),))

                if f not in faces_0:
                    faces_0.append(f)

            except:
                pass

        y_start = y_end

    if len(faces_0) > 0:
        p.Set(faces=faces_0, name='Ply_0_Set')

    # ============================================================
    # تخصیص استوکستیک متریال‌ها برای کل طول مدل
    # ============================================================
    faces_by_mat = {i: [] for i in range(len(VF_LEVELS))}
    all_cells_data = []

    # محاسبه مرزهای X برای تمام طول مدل
    dy = 0.0
    for item in layup:
        if item[0] == 90:
            dy = item[1] / float(n_cells_thickness)
            break
    # dx همیشه برابر dy (سلول‌های مربعی)
    dx = dy

    x_bounds = [0.0]
    current_x = 0.0
    while True:
        current_x += dx
        if current_x >= L - 1e-5:
            break
        x_bounds.append(current_x)
    x_bounds.append(L)

    x_centers = []
    for k in range(len(x_bounds) - 1):
        x_centers.append((x_bounds[k] + x_bounds[k + 1]) / 2.0)

    y_start = 0.0
    for ply_idx, item in enumerate(layup):
        angle = item[0]
        t = item[1]
        y_end = y_start + t

        if angle == 90:
            y_mid_ply = y_start + (t / 2.0)
            for j in range(n_cells_thickness):
                y_cell_center = y_start + (j + 0.5) * dy
                normalized_dist = abs(y_cell_center - y_mid_ply) / (t / 2.0)
                deterministic_score = (1.0 - (normalized_dist ** 2)) * 90.0

                for x_cell_center in x_centers:
                    noise = random.uniform(-15.0, 15.0)
                    raw_score = deterministic_score + noise

                    all_cells_data.append({
                        'x': x_cell_center,
                        'y': y_cell_center,
                        'score': raw_score
                    })

        y_start = y_end

    # اعمال میانگین کل
    # نکته: از _py_sum استفاده می‌کنیم برای جلوگیری از shadow شدن توسط Abaqus
    mean_score = _py_sum([cell['score'] for cell in all_cells_data]) / float(len(all_cells_data))

    for cell in all_cells_data:
        shifted_vf = cell['score'] - mean_score + TARGET_VF
        shifted_vf = max(0.0, min(90.0, shifted_vf))

        best_idx = 0
        min_diff = 1000.0
        for idx, vf_val in enumerate(VF_LEVELS):
            diff = abs(shifted_vf - vf_val)
            if diff < min_diff:
                min_diff = diff
                best_idx = idx

        try:
            face_obj = p.faces.findAt(((cell['x'], cell['y'], 0.0),))
            if face_obj is not None:
                faces_by_mat[best_idx].append(face_obj)
        except:
            pass

    # ایجاد ست‌ها در آباکوس (نام‌ها تا دو رقم اعشار با _ جدا می‌شوند تا دقیق باشند)
    for idx, vf_val in enumerate(VF_LEVELS):
        face_list = faces_by_mat[idx]
        if len(face_list) > 0:
            # مثال خروجی: Set_90deg_Vf_14_50
            str_vf = "{:.2f}".format(vf_val).replace('.', '_')
            set_name = 'Set_90deg_Vf_{}'.format(str_vf)
            p.Set(faces=face_list, name=set_name)
            print("  [OK] Created {} with {} cells".format(set_name, len(face_list)))

    # ============================================================
    # ساخت ست لبه‌های ترک (تنها محدود به ناحیه Gauge)
    # ============================================================
    print("")
    print("  Creating Potential_Crack_Edges set...")

    x_gauge_start = (L - L_gauge) / 2.0
    x_gauge_end = x_gauge_start + L_gauge

    # فیلتر کردن خطوط عمودی که فقط داخل محدوده گیج هستند
    ##########
    # -----------------------------------------------
    # Select only the required crack edges
    # -----------------------------------------------

    # تمام مرزهای سلول داخل ناحیه Gauge
    candidate_edges = [
        x for x in x_bounds
        if (x_gauge_start - 1e-5) <= x <= (x_gauge_end + 1e-5)
    ]

    # ضخامت کل لایه‌های 90
    t90_total = 0.0
    for angle, t in layup:
        if angle == 90:
            t90_total += t

    # تعداد ترک بر اساس CRACK_SELECTION_MODE
    if CRACK_SELECTION_MODE == 'FIXED_SPACING':
        # cracks هر CRACK_SPACING_MM یکبار
        n_cracks = max(1, int(round(L / CRACK_SPACING_MM)))
    else:  # RHO_BASED (پیش‌فرض)
        # n_cracks = rho * L  (طبق مقاله — rho = cracks per unit LENGTH)
        n_cracks = max(1, int(round(rho * L)))

    # بیشتر از تعداد مرزهای موجود نشود
    n_cracks = min(n_cracks, len(candidate_edges))

    crack_x_positions = []

    if n_cracks > 0:

        # انتخاب یکنواخت از بین مرزهای سلول
        if n_cracks == 1:
            crack_x_positions.append(candidate_edges[len(candidate_edges) // 2])
        else:
            for i in range(n_cracks):
                idx = int(round(i * (len(candidate_edges) - 1) / float(n_cracks - 1)))
                crack_x_positions.append(candidate_edges[idx])
    #########

    y_ranges_90 = []
    y_start = 0.0
    for item in layup:
        angle = item[0]
        t = item[1]
        y_end = y_start + t
        if angle == 90:
            y_ranges_90.append((y_start, y_end))
        y_start = y_end

    # ============================================================
    # اصلاح مهم: انتخاب تمام edge های عمودی در لایه‌های ۹۰°
    # ============================================================
    # نسخهٔ قبلی فقط یک edge در y_mid هر لایه ۹۰° انتخاب می‌کرد (وسط لایه)،
    # در حالی که هر مسیر ترک باید تمام ضخامت لایه ۹۰° رو پوشش بده. یعنی به
    # ازای هر مسیر ترک در x_pos و هر لایه ۹۰°، باید n_cells_thickness تا edge
    # انتخاب بشه (هر کدوم به اندازه dy ضخامت دارن).
    #
    # مثال با n90=1, symmetric, t90=0.25, n_cells_thickness=5:
    #   layup = [0/90/90/0]  →  2 لایه ۹۰° مجاور
    #   هر لایه ۹۰° به ۵ زیرسلول تقسیم شده
    #   هر مسیر ترک باید ۲*۵ = ۱۰ edge داشته باشه
    #   با n_cracks=20 → ۲۰۰ edge کل (به‌جای ۴۰ در نسخهٔ قبلی)
    #
    # استراتژی: تک‌گذری روی p.edges با سه فیلتر:
    #   1) cx در crack_x_set (فقط مسیرهای ترک انتخابی)
    #   2) طول edge در حد dy (فقط edge های عمودی، حذف edge های افقی بلند)
    #   3) cy در بازهٔ لایه‌های ۹۰° (تمام ضخامت)
    #
    # نکته مهم Abaqus: متد getCentroid() برای Edge وجود ندارد!
    # باید از edge.pointOn[0] یا میانگین vertices استفاده کرد.
    # ============================================================

    # محاسبه dy (ضخامت هر زیرسلول در لایه ۹۰°)
    dy = 0.0
    for item in layup:
        if item[0] == 90:
            dy = item[1] / float(n_cells_thickness)
            break

    # مجموعه‌ای از x_positions برای lookup سریع O(1)
    crack_x_set = set([round(x, 4) for x in crack_x_positions])

    # تعداد مورد انتظار edge های per crack path
    n_90_ply_groups = len(y_ranges_90)
    expected_per_crack = n_90_ply_groups * n_cells_thickness

    print("  [INFO] Crack paths: {}".format(len(crack_x_positions)))
    print("  [INFO] 90° ply groups: {}".format(n_90_ply_groups))
    print("  [INFO] Subcells per 90° ply: {}".format(n_cells_thickness))
    print("  [INFO] Expected edges per crack path: {}".format(expected_per_crack))
    print("  [INFO] Expected total edges: ~{}".format(
        expected_per_crack * len(crack_x_positions)))

    # تک‌گذری روی p.edges
    crack_edges = []
    n_total_edges = len(p.edges)
    n_skipped_horizontal = 0
    n_skipped_not_in_90 = 0
    n_skipped_wrong_x = 0
    n_skipped_no_coords = 0

    print("  Scanning {} edges (single-pass)...".format(n_total_edges))

    for edge in p.edges:
        # ============================================================
        # محاسبه centroid (میانگین vertices) — Abaqus-safe
        # ============================================================
        # نکته مهم: edge.getCentroid() در Abaqus وجود ندارد!
        # روش استاندارد: استفاده از edge.pointOn[0] که یک tuple (x, y, z) برمی‌گرداند
        # fallback: میانگین vertices
        cx = None
        cy = None

        # روش ۱: edge.pointOn (روش استاندارد Abaqus)
        try:
            point_on = edge.pointOn  # = ((x, y, z), parameter)
            if point_on and len(point_on) >= 1:
                pt = point_on[0]
                if pt and len(pt) >= 2:
                    cx = float(pt[0])
                    cy = float(pt[1])
        except Exception:
            pass

        # روش ۲: میانگین vertices (اگر pointOn کار نکرد)
        if cx is None or cy is None:
            try:
                verts = edge.getVertices()
                if verts and len(verts) >= 2:
                    v1 = p.vertices[verts[0]]
                    v2 = p.vertices[verts[1]]
                    p1 = v1.pointOn[0]
                    p2 = v2.pointOn[0]
                    cx = (float(p1[0]) + float(p2[0])) / 2.0
                    cy = (float(p1[1]) + float(p2[1])) / 2.0
            except Exception:
                pass

        if cx is None or cy is None:
            n_skipped_no_coords += 1
            continue

        # فیلتر ۱: cx باید در crack_x_set باشه
        cx_rounded = round(cx, 4)
        if cx_rounded not in crack_x_set:
            n_skipped_wrong_x += 1
            continue

        # فیلتر ۲: تشخیص edge عمودی با استفاده از vertices
        # ============================================================
        # نکته: یک edge عمودی است اگر x هر دو vertex برابر باشد (dx ≈ 0).
        # این روش مطمئن‌تر از استفاده از طول edge است چون در مدل ما
        # dx == dy (هم مربعی)، پس تشخیص بر اساس طول ممکنه اشتباه کنه.
        # ============================================================
        is_vertical = False
        try:
            verts = edge.getVertices()
            if verts and len(verts) >= 2:
                v1 = p.vertices[verts[0]]
                v2 = p.vertices[verts[1]]
                p1 = v1.pointOn[0]
                p2 = v2.pointOn[0]
                dx_v = abs(float(p2[0]) - float(p1[0]))
                # یک edge عمودی است اگر تغییر x آن تقریباً صفر باشد
                if dx_v < 1e-6:
                    is_vertical = True
        except Exception:
            # fallback: استفاده از طول edge
            try:
                edge_length = float(edge.getLength())
                if edge_length <= 2.0 * dy:
                    is_vertical = True
            except Exception:
                pass

        if not is_vertical:
            n_skipped_horizontal += 1
            continue

        # فیلتر ۳: cy باید در بازهٔ یکی از لایه‌های ۹۰° باشه (تمام ضخامت)
        in_90_layer = False
        for (y_min, y_max) in y_ranges_90:
            if y_min - 1e-6 <= cy <= y_max + 1e-6:
                in_90_layer = True
                break

        if in_90_layer:
            crack_edges.append(edge)
        else:
            n_skipped_not_in_90 += 1

    print("  [INFO] Filtered: {} vertical 90° edges found".format(len(crack_edges)))
    print("  [INFO] Skipped: {} wrong-x, {} horizontal, {} outside 90°, {} no-coords".format(
        n_skipped_wrong_x, n_skipped_horizontal, n_skipped_not_in_90, n_skipped_no_coords))

    # ============================================================
    # ساخت Set با regionToolset.Region (روش استاندارد Abaqus)
    # ============================================================
    # نکته مهم: p.Set(edges=python_list) در برخی نسخه‌های Abaqus کار نمی‌کند
    # و یک set خالی ایجاد می‌کند. روش استاندارد استفاده از regionToolset.Region
    # است که یک EdgeArray قبول می‌کند.
    # ============================================================
    if len(crack_edges) > 0:
        try:
            # روش ۱: استفاده از regionToolset.Region با edges
            region = regionToolset.Region(edges=crack_edges)
            p.Set(name='Potential_Crack_Edges', region=region)
            print("  [OK] Created 'Potential_Crack_Edges' with {} edges (via regionToolset)".format(
                len(crack_edges)))
        except Exception as e1:
            print("  [WARN] regionToolset.Region failed: {}".format(e1))
            # روش ۲: fallback با p.Set مستقیم
            try:
                p.Set(edges=crack_edges, name='Potential_Crack_Edges')
                print("  [OK] Created 'Potential_Crack_Edges' with {} edges (via direct Set)".format(
                    len(crack_edges)))
            except Exception as e2:
                print("  [ERROR] p.Set failed: {}".format(e2))
                # روش ۳: fallback با findAt (روش قبلی، کندتر)
                print("  [INFO] Falling back to findAt method...")
                try:
                    # ساخت نقاط findAt از centroid های edge های پیدا شده
                    findat_points = []
                    for edge in crack_edges:
                        try:
                            pt = edge.pointOn[0]
                            findat_points.append(((float(pt[0]), float(pt[1]), 0.0),))
                        except Exception:
                            continue
                    if len(findat_points) > 0:
                        crack_edges_fa = p.edges.findAt(*findat_points)
                        p.Set(edges=crack_edges_fa, name='Potential_Crack_Edges')
                        print("  [OK] Created 'Potential_Crack_Edges' via findAt fallback ({} edges)".format(
                            len(findat_points)))
                    else:
                        print("  [ERROR] No valid points for findAt")
                except Exception as e3:
                    print("  [ERROR] All Set creation methods failed: {}".format(e3))

        # بررسی تطابق با تعداد مورد انتظار
        expected_total = expected_per_crack * len(crack_x_positions)
        if len(crack_edges) == expected_total:
            print("  [OK] Edge count matches expected value ({})".format(expected_total))
        else:
            print("  [WARN] Edge count ({}) differs from expected ({})".format(
                len(crack_edges), expected_total))
    else:
        print("  [WARN] No crack edges found!")
        print("  [INFO] Diagnostic:")
        print("    - Check if crack_x_positions is non-empty: {}".format(len(crack_x_positions)))
        print("    - Check if y_ranges_90 is non-empty: {}".format(len(y_ranges_90)))
        print("    - Check if partitions were applied (p.edges count: {})".format(n_total_edges))


# ============================================================
# CREATE MATERIALS + SECTIONS + SECTION ASSIGNMENTS  [NEW]
# ============================================================

def _safe_material_name(prefix, vf_value):
    """تولید نام Abaqus-safe از prefix و مقدار Vf."""
    text = ('%s_%05.2f' % (prefix, float(vf_value))).replace('-', 'm')
    return text.replace('.', '_')


def _create_engineering_material(model, name, props, orientation):
    """ساخت متریال orthotropic elastic با ENGINEERING_CONSTANTS.

    برای مدل 2D (plane-strain / plane-stress) در صفحه X-Y:
      - 0deg  : fiber along local axis-1 (X جهانی)
                جدول: (E11, E22, E22, nu12, nu12, nu23, G12, G12, G23)
                فرض transversely isotropic: E3=E2, nu13=nu12, G13=G12

      - 90deg : fiber along local axis-3 (Z جهانی، out-of-plane)
                جدول: (E22, E22, E11, nu23, nu21, nu21, G23, G12, G12)
                با nu21 = nu12 * E22/E11  (Poisson فرعی)
                این الگو از build_mesoscale_model.py (repo مقاله) عیناً برداشت شده.

    نکته: متریال‌های از پیش موجود دوباره ساخته نمی‌شوند (idempotent).
    """
    if name in model.materials.keys():
        return

    model.Material(name=name)

    # محاسبه ضریب پواسون فرعی برای پایداری ترمودینامیکی آباکوس
    # (Drucker stability: nu21 = nu12 * E22/E11)
    nu21 = props['nu12'] * (props['E22'] / props['E11'])

    if orientation == '0deg':
        # fiber along axis 1 (X جهانی)
        table = ((props['E11'], props['E22'], props['E22'],
                  props['nu12'], props['nu12'], props['nu23'],
                  props['G12'], props['G12'], props['G23']),)
    elif orientation == '90deg':
        # fiber along axis 3 (Z جهانی، out-of-plane در مدل 2D)
        table = ((props['E22'], props['E22'], props['E11'],
                  props['nu23'], nu21, nu21,
                  props['G23'], props['G12'], props['G12']),)
    else:
        raise ValueError("orientation must be '0deg' or '90deg'")

    model.materials[name].Elastic(type=ENGINEERING_CONSTANTS, table=table)


def _create_solid_section(model, section_name, material_name):
    """ساخت HomogeneousSolidSection اگر از قبل وجود نداشته باشد."""
    if section_name in model.sections.keys():
        return
    model.HomogeneousSolidSection(
        name=section_name,
        material=material_name,
        thickness=None  # ضخامت از خود هندسه برداشته می‌شود (2D)
    )


def build_materials_and_sections(p, model, layup):
    """
    Stage 5: ساخت متریال‌ها، sectionها و اختصاص آن‌ها به face sets.

    ورودی‌ها:
      p     : Part مورد نظر (با setهای از قبل ساخته‌شده)
      model : Abaqus model
      layup : لیست لایه‌ها

    خروجی:
      - 1 متریال + 1 section برای Ply_0_Set (Vf=45%, fiber along X)
      - به ازای هر VF_LEVELS: 1 متریال + 1 section برای Set_90deg_Vf_*
      - SectionAssignment برای هر set
    """
    print("")
    print("=" * 70)
    print("Stage 5: Materials + Sections + Section Assignments")
    print("=" * 70)

    # ----------------------------------------------------------
    # 5.1) متریال لایهٔ 0° (یکنواخت با Vf=45%)
    # ----------------------------------------------------------
    print("")
    print("--- 5.1: Creating 0deg material (Vf=45%, fiber along X) ---")

    vf_0 = 45.0  # Vf اسمی برای لایه‌های 0°
    props_0 = get_properties(vf_0, units='MPa')

    mat_name_0 = _safe_material_name('Mat_0deg_Vf', vf_0)
    sec_name_0 = _safe_material_name('Sec_0deg_Vf', vf_0)

    print("  Material: {}".format(mat_name_0))
    print("    E11 = {:.2f} MPa, E22 = {:.2f} MPa, nu12 = {:.4f}, G12 = {:.2f} MPa".format(
        props_0['E11'], props_0['E22'], props_0['nu12'], props_0['G12']))

    _create_engineering_material(model, mat_name_0, props_0, '0deg')
    _create_solid_section(model, sec_name_0, mat_name_0)
    print("  [OK] Material + Section created for 0deg ply")

    # Section assignment برای Ply_0_Set
    if 'Ply_0_Set' in p.sets.keys():
        p.SectionAssignment(
            region=regionToolset.Region(faces=p.sets['Ply_0_Set'].faces),
            sectionName=sec_name_0
        )
        print("  [OK] Section '{}' assigned to 'Ply_0_Set' ({} faces)".format(
            sec_name_0, len(p.sets['Ply_0_Set'].faces)))
    else:
        print("  [WARN] 'Ply_0_Set' not found! Section not assigned for 0deg ply.")

    # ----------------------------------------------------------
    # 5.2) متریال‌های لایهٔ 90° (به ازای هر VF_LEVEL)
    # ----------------------------------------------------------
    print("")
    print("--- 5.2: Creating 90deg materials (one per VF_LEVEL) ---")
    print("  VF_LEVELS = {}".format(VF_LEVELS))
    print("  (For Vf values between Table 1 points, linear interpolation is used)")

    n_mat_created = 0
    n_sec_assigned = 0

    for idx, vf_val in enumerate(VF_LEVELS):
        props_90 = get_properties(vf_val, units='MPa')

        mat_name_90 = _safe_material_name('Mat_90deg_Vf', vf_val)
        sec_name_90 = _safe_material_name('Sec_90deg_Vf', vf_val)

        # نام set متناظر (مثل Set_90deg_Vf_45_00)
        str_vf = "{:.2f}".format(vf_val).replace('.', '_')
        set_name = 'Set_90deg_Vf_{}'.format(str_vf)

        # ساخت متریال + section (idempotent)
        _create_engineering_material(model, mat_name_90, props_90, '90deg')
        _create_solid_section(model, sec_name_90, mat_name_90)

        print("  [{}] Vf={:6.2f}% -> Mat: {}, Sec: {}".format(
            idx, vf_val, mat_name_90, sec_name_90))
        print("        E11={:.2f}, E22={:.2f}, nu12={:.4f}, G12={:.2f}, G23={:.2f} MPa".format(
            props_90['E11'], props_90['E22'], props_90['nu12'],
            props_90['G12'], props_90['G23']))

        # Section assignment به set مربوطه
        if set_name in p.sets.keys():
            faces_in_set = p.sets[set_name].faces
            if len(faces_in_set) > 0:
                p.SectionAssignment(
                    region=regionToolset.Region(faces=faces_in_set),
                    sectionName=sec_name_90
                )
                print("        [OK] Assigned to '{}' ({} faces)".format(
                    set_name, len(faces_in_set)))
                n_sec_assigned += 1
            else:
                print("        [WARN] Set '{}' is empty".format(set_name))
        else:
            print("        [WARN] Set '{}' not found (no faces for this Vf)".format(set_name))

        n_mat_created += 1

    print("")
    print("  Summary: {} materials created, {} sections assigned to sets".format(
        n_mat_created + 1, n_sec_assigned + 1))
    print("  Total materials in model: {}".format(len(model.materials.keys())))
    print("  Total sections in model:  {}".format(len(model.sections.keys())))


# ============================================================
# ASSIGN MATERIAL ORIENTATION  [NEW]
# ============================================================

def assign_material_orientation(p):
    """
    Stage 6: اختصاص Material Orientation به همهٔ faces.

    در مدل 2D planar با GLOBAL orientation و AXIS_3:
      - local 1 = global X
      - local 2 = global Y
      - local 3 = global Z (out-of-plane)

    این یعنی متریال‌های 90deg که fiber را در axis 3 تعریف کرده‌ایم،
    در واقع fiber را در جهت Z (out-of-plane) قرار می‌دهند — که برای
    cross-section 2D از لایه‌چینی [0/90]s صحیح است.

    تابع idempotent نیست؛ اگر از قبل orientation وجود داشته باشد،
    Abaqus یک orientation جدید اضافه می‌کند.
    """
    print("")
    print("=" * 70)
    print("Stage 6: Material Orientation (GLOBAL, AXIS_3)")
    print("=" * 70)

    all_faces = p.faces
    if len(all_faces) == 0:
        print("  [WARN] No faces in part; skipping orientation")
        return

    try:
        p.MaterialOrientation(
            region=regionToolset.Region(faces=all_faces),
            orientationType=GLOBAL,
            axis=AXIS_3,
            additionalRotationType=ROTATION_NONE,
            localCsys=None,
            fieldName='',
            stackDirection=STACK_3
        )
        print("  [OK] MaterialOrientation applied to {} faces (GLOBAL, AXIS_3)".format(
            len(all_faces)))
    except (TypeError, Exception) as e1:
        print("  [WARN] Primary MaterialOrientation signature failed: {}".format(e1))
        # Fallback با امضای ساده‌تر
        try:
            p.MaterialOrientation(
                region=regionToolset.Region(faces=all_faces),
                orientationType=GLOBAL,
                axis=AXIS_3
            )
            print("  [OK] MaterialOrientation applied (fallback signature)")
        except Exception as e2:
            print("  [ERROR] MaterialOrientation failed: {}".format(e2))


# ============================================================
# STAGE 7: MESH GENERATION - تولید شبکه
# ============================================================

def generate_mesh(p, model, element_size=None):
    """
    Stage 7: تولید mesh برای continuum part.

    - seedPart با اندازه المان مشخص
    - setElementType برای همهٔ faces به CPE4R یا CPS4R
    - generateMesh

    نکته: element_size پیش‌فرض هم‌اندازه با dy است تا با partitions هم‌راستا باشد.
    """
    print("")
    print("=" * 70)
    print("Stage 7: Mesh Generation")
    print("=" * 70)

    if element_size is None:
        element_size = mesh_element_size

    print("  Element size: {} mm".format(element_size))
    print("  Analysis type: {} -> element: {}".format(
        analysis_type, 'CPE4R' if analysis_type == 'PLANE_STRAIN' else 'CPS4R'))

    # مرحله ۱: seedPart
    try:
        p.seedPart(size=element_size, deviationFactor=0.1, minSizeFactor=0.1)
        print("  [OK] Part seeded (size={})".format(element_size))
    except Exception as e:
        print("  [ERROR] seedPart failed: {}".format(e))
        return False

    # مرحله ۲: setElementType برای continuum (CPE4R یا CPS4R)
    try:
        if analysis_type == 'PLANE_STRAIN':
            elem_type = mesh.ElemType(elemCode=CPE4R, elemLibrary=STANDARD)
        else:
            elem_type = mesh.ElemType(elemCode=CPS4R, elemLibrary=STANDARD)

        # اعمال روی همهٔ faces
        face_region = regionToolset.Region(faces=p.faces)
        p.setElementType(regions=face_region, elemTypes=(elem_type,))
        print("  [OK] Element type set ({})".format(
            'CPE4R' if analysis_type == 'PLANE_STRAIN' else 'CPS4R'))
    except Exception as e:
        print("  [ERROR] setElementType failed: {}".format(e))
        return False

    # مرحله ۳: generateMesh
    try:
        p.generateMesh()
        n_nodes = len(p.nodes)
        n_elements = len(p.elements)
        print("  [OK] Mesh generated: {} nodes, {} elements".format(n_nodes, n_elements))
        return True
    except Exception as e:
        print("  [ERROR] generateMesh failed: {}".format(e))
        return False


# ============================================================
# STAGE 8: COHESIVE MATERIAL + SECTION
# ============================================================

def create_cohesive_material(model):
    """
    Stage 8.1: ساخت متریال cohesive با قانون bilinear traction-separation.

    - Elastic: TRACTION با K_n = K_s = K_t = penalty_stiffness
    - MaxsDamageInitiation: T_n^0 = T_s^0 = T_t^0 = cohesive_strength
    - DamageEvolution: ENERGY, LINEAR softening, G_c = cohesive_fracture_energy

    نکته: viscosity در اینجا اضافه نمی‌شه چون برای TRACTION_SEPARATION
    cohesive، باید از *SECTION CONTROLS استفاده بشه (در create_cohesive_section).
    """
    print("")
    print("--- 8.1: Creating Cohesive Material ---")

    if cohesive_material_name in model.materials.keys():
        print("  [INFO] Cohesive material '{}' already exists, skipping".format(
            cohesive_material_name))
        return model.materials[cohesive_material_name]

    try:
        material = model.Material(name=cohesive_material_name)

        # Elastic: TRACTION
        material.Elastic(
            type=TRACTION,
            table=((cohesive_penalty_stiffness,
                    cohesive_penalty_stiffness,
                    cohesive_penalty_stiffness),)
        )

        # Damage Initiation: Max Stress
        material.MaxsDamageInitiation(
            table=((cohesive_strength, cohesive_strength, cohesive_strength),)
        )

        # Damage Evolution: Energy, Linear softening
        material.maxsDamageInitiation.DamageEvolution(
            type=ENERGY,
            softening=LINEAR,
            table=((cohesive_fracture_energy,),)
        )

        print("  [OK] Cohesive material '{}' created".format(cohesive_material_name))
        print("    Strength (YT): {} MPa".format(cohesive_strength))
        print("    Fracture energy (G_c): {} N/mm".format(cohesive_fracture_energy))
        print("    Penalty stiffness (K): {} MPa/mm".format(cohesive_penalty_stiffness))
        return material

    except Exception as e:
        print("  [ERROR] Cohesive material creation failed: {}".format(e))
        return None


def create_cohesive_section(model):
    """
    Stage 8.2: ساخت CohesiveSection با Specify thickness + Section Controls viscosity.

    تنظیمات دقیقاً مطابق UI Abaqus:
      - Initial thickness: Specify → 0.001 mm
        (یک عدد کوچک برای المان‌های cohesive zero-thickness)
      - Response: Traction-Separation
      - Element Controls → Viscosity: Specify → 1e-4
        (تنها راه برای اعمال viscosity به traction-separation cohesive)

    نکته مهم: viscosity در TRACTION_SEPARATION cohesive نمی‌تونه از طریق
    *DAMAGE STABILIZATION در متریال اضافه بشه. باید حتماً از طریق
    *SECTION CONTROLS در section باشه. این تابع چند fallback امتحان می‌کنه
    و اگه همه شکست بخورن، راهنمای Keyword Editor صریح چاپ می‌کنه.
    """
    print("")
    print("--- 8.2: Creating Cohesive Section ---")

    # اگه از قبل وجود داره، حذف کن تا دوباره بسازیم (با viscosity)
    if cohesive_section_name in model.sections.keys():
        del model.sections[cohesive_section_name]
        print("  [INFO] Deleted existing section (recreating with viscosity)")

    # ============================================================
    # مرحله ۱: ساخت CohesiveSection با Initial thickness = Specify
    # ============================================================
    # در UI Abaqus: Initial thickness: Specify, Value: cohesive_initial_thickness
    # معادل API: initialThicknessType=SPECIFY, initialThickness=cohesive_initial_thickness
    #
    # نکته: ANALYTICAL هم کار می‌کنه ولی فقط برای المان‌هایی که از geometry
    # ضخامت می‌گیرن. چون المان‌های cohesive ما zero-thickness هستن،
    # باید از Specify با مقدار صریح استفاده کنیم.
    # ============================================================
    section_created = False
    try:
        # روش ۱: initialThicknessType=SPECIFY (مطابق UI)
        model.CohesiveSection(
            name=cohesive_section_name,
            material=cohesive_material_name,
            response=TRACTION_SEPARATION,
            initialThicknessType=SPECIFY,
            initialThickness=cohesive_initial_thickness
        )
        print("  [OK] CohesiveSection created (Initial thickness: Specify, t={} mm)".format(
            cohesive_initial_thickness))
        section_created = True
    except Exception as e1:
        print("  [WARN] initialThicknessType=SPECIFY failed: {}".format(e1))
        # روش ۲: ANALYTICAL fallback
        try:
            model.CohesiveSection(
                name=cohesive_section_name,
                material=cohesive_material_name,
                response=TRACTION_SEPARATION,
                initialThicknessType=ANALYTICAL,
                initialThickness=cohesive_initial_thickness
            )
            print("  [OK] CohesiveSection created (ANALYTICAL fallback, t={} mm)".format(
                cohesive_initial_thickness))
            section_created = True
        except Exception as e2:
            print("  [WARN] ANALYTICAL thickness failed: {}".format(e2))
            # روش ۳: GEOMETRY fallback (آخرین راه)
            try:
                model.CohesiveSection(
                    name=cohesive_section_name,
                    material=cohesive_material_name,
                    response=TRACTION_SEPARATION,
                    initialThicknessType=GEOMETRY
                )
                print("  [OK] CohesiveSection created (GEOMETRY last resort)")
                print("  [WARN] GEOMETRY type may cause zero-thickness errors")
                section_created = True
            except Exception as e3:
                print("  [ERROR] CohesiveSection creation failed: {}".format(e3))
                return False

    if not section_created:
        return False

    # ============================================================
    # مرحله ۲: افزودن Section Controls (Element Controls) برای viscosity
    # ============================================================
    # در UI Abaqus: Section → Edit → Element Controls → Viscosity: Specify, 1e-4
    # معادل API: section.SectionControls(viscosity=1e-4)
    #
    # نکته مهم: نام keyword در نسخه‌های مختلف Abaqus متفاوت است.
    # چند fallback امتحان می‌شه:
    #   1. section.SectionControls(viscosity=...)
    #   2. section.SectionControls(stabilizationCoefficient=...)
    #   3. section.SectionControls(dampingViscosity=...)
    #   4. section.SectionControls(cohesiveViscosity=...)
    #   5. model.SectionControls(name=..., viscosity=...)
    #   6. fallback نهایی: Keyword Editor دستی
    # ============================================================
    section = model.sections[cohesive_section_name]
    viscosity_added = False
    used_keyword = None

    viscosity_keywords = ['viscosity', 'stabilizationCoefficient',
                          'dampingViscosity', 'cohesiveViscosity']
    for kw in viscosity_keywords:
        try:
            kwargs = {'viscosity': cohesive_viscosity} if kw == 'viscosity' else {kw: cohesive_viscosity}
            section.SectionControls(**kwargs)
            print("  [OK] Viscosity added via SectionControls (keyword='{}', value={})".format(
                kw, cohesive_viscosity))
            viscosity_added = True
            used_keyword = kw
            break
        except (TypeError, Exception):
            continue

    # تلاش با model.SectionControls اگه هیچ کدوم از section.SectionControls کار نکرد
    if not viscosity_added:
        try:
            model.SectionControls(name='Coh_Sec_Controls', viscosity=cohesive_viscosity)
            print("  [OK] Viscosity added via model.SectionControls (value={})".format(
                cohesive_viscosity))
            viscosity_added = True
            used_keyword = 'model.SectionControls'
        except Exception:
            pass

    # راهنمای صریح اگه همهٔ روش‌های API شکست بخورن
    if not viscosity_added:
        print("")
        print("  [WARN] Could not auto-add viscosity via Section Controls API")
        print("  [INFO] Viscosity MUST be added manually via Keyword Editor:")
        print("         -----------------------------------------------")
        print("         1. Model → Edit Keywords...")
        print("         2. Find the *Cohesive Section block for '{}'".format(cohesive_section_name))
        print("         3. Add immediately AFTER the section line:")
        print("            *Section Controls, Name=Coh_Sec_Controls")
        print("            {}, , , , , , ,".format(cohesive_viscosity))
        print("         4. Save the keywords")
        print("         -----------------------------------------------")
        print("         OR via GUI:")
        print("         Property module → Section → {} → Edit → Element Controls".format(cohesive_section_name))
        print("         → Viscosity: Specify → {}".format(cohesive_viscosity))
        print("")

    return True


def build_cohesive_material_and_section(model):
    """Stage 8: ساخت cohesive material + section (با fallback های لازم)."""
    print("")
    print("=" * 70)
    print("Stage 8: Cohesive Material + Section")
    print("=" * 70)
    create_cohesive_material(model)
    create_cohesive_section(model)


# ============================================================
# STAGE 9: SAVE CAE - ذخیره فایل .cae
# ============================================================
# نکته مهم: مرحلهٔ Orphan Mesh حذف شد چون برای مدل ما فایده‌ای ندارد.
# ابزار 'Insert cohesive seams' روی هندسه (geometry) کار می‌کند، نه روی
# orphan mesh. همچنین Instance مستقیماً از part اصلی (Laminate) ساخته
# می‌شود. ساخت orphan mesh تنها در صورتی لازم است که بخواهیم بعد از
# درج cohesive elements، section assignment را روی المان‌های orphan انجام
# دهیم — که در این pipeline لازم نیست.
# ============================================================

def save_cae(model_name_str=None, file_path=None):
    """
    Stage 10: ذخیره فایل .cae برای اجرای دستی در CAE.

    فایل در مسیر مشخص شده ذخیره می‌شه. اگر file_path داده نشه،
    در کنار اسکریپت با نام مدل ذخیره می‌شه.
    """
    print("")
    print("=" * 70)
    print("Stage 10: Save CAE")
    print("=" * 70)

    if model_name_str is None:
        model_name_str = model_name

    if file_path is None:
        # ذخیره در مسیر فعلی
        file_path = '{}.cae'.format(model_name_str)

    try:
        mdb.saveAs(file_path)
        print("  [OK] CAE saved: {}".format(file_path))
        return True
    except Exception as e:
        print("  [ERROR] saveAs failed: {}".format(e))
        # تلاش با save
        try:
            mdb.save()
            print("  [OK] CAE saved (existing file)")
            return True
        except Exception as e2:
            print("  [ERROR] save also failed: {}".format(e2))
            return False


# ============================================================
# STAGE 11: POST-MANUAL COHESIVE - پردازش CohesiveSeam-1-Elements
# ============================================================

def process_manual_cohesive(model, p):
    """
    Stage 11: پردازش CohesiveSeam-1-Elements بعد از درج دستی cohesive.

    این تابع بعد از اینکه کاربر در CAE با ابزار 'Insert cohesive seams'
    المان‌های COH2D4 درج کرد، فراخوانی می‌شه.

    کارها:
    1. اطمینان از وجود Cohesive_Mat و Cohesive_Sec
    2. تشخیص part مورد نظر (Laminate)
    3. force کردن Element Type به COH2D4 روی CohesiveSeam-1-Elements
    4. Assign کردن Cohesive_Sec به این set
    5. اطمینان از Material Orientation روی همهٔ elements

    نام set که ابزار Insert cohesive seams می‌سازه معمولاً یکی از اینهاست:
    - 'CohesiveSeam-1-Elements' (پیش‌فرض)
    - 'CohesiveSeam-2-Elements' (اگه دوبار اجرا شده باشه)
    - یا نام دلخواه کاربر
    """
    print("")
    print("=" * 70)
    print("Stage 11: Process Manual Cohesive Elements")
    print("=" * 70)

    # 1. اطمینان از وجود Cohesive_Mat و Cohesive_Sec
    build_cohesive_material_and_section(model)

    # 2. تشخیص part (فقط geometry — orphan mesh حذف شد)
    if part_name not in model.parts.keys():
        print("  [ERROR] Part '{}' not found!".format(part_name))
        print("  [INFO] Did you run 'build' mode first?")
        return False
    part_to_use = model.parts[part_name]
    print("  [INFO] Using geometric part: {}".format(part_name))

    # 3. پیدا کردن set با نام CohesiveSeam-*-Elements
    coh_set = None
    coh_set_name = None
    for sname in part_to_use.sets.keys():
        if sname.startswith('CohesiveSeam') and sname.endswith('Elements'):
            coh_set = part_to_use.sets[sname]
            coh_set_name = sname
            print("  [INFO] Found cohesive seam set: '{}'".format(sname))
            break

    if coh_set is None:
        print("  [WARN] No 'CohesiveSeam-*-Elements' set found!")
        print("  [INFO] Available sets:")
        for sname in sorted(part_to_use.sets.keys()):
            print("    - {}".format(sname))
        print("")
        print("  [INFO] Did you run 'Insert cohesive seams' in CAE?")
        print("  [INFO] If yes, check the set name and adjust if needed.")
        return False

    # 4. Force Element Type به COH2D4
    print("")
    print("  Forcing Element Type to COH2D4 on '{}'...".format(coh_set_name))
    try:
        elem_type = mesh.ElemType(elemCode=COH2D4, elemLibrary=STANDARD)
        part_to_use.setElementType(regions=(coh_set,), elemTypes=(elem_type,))
        print("  [OK] Element type forced to COH2D4")
    except Exception as e:
        print("  [WARN] setElementType failed: {}".format(e))
        # Fallback با Region
        try:
            region = regionToolset.Region(elements=coh_set.elements)
            part_to_use.setElementType(regions=region, elemTypes=(elem_type,))
            print("  [OK] Element type forced via Region fallback")
        except Exception as e2:
            print("  [ERROR] Both setElementType attempts failed: {}".format(e2))

    # 5. Assign Cohesive_Sec به set
    print("")
    print("  Assigning Cohesive_Sec to '{}'...".format(coh_set_name))
    try:
        # تلاش با kwargs کامل
        part_to_use.SectionAssignment(
            region=coh_set,
            sectionName=cohesive_section_name,
            offset=0.0,
            offsetType=MIDDLE_SURFACE,
            offsetField='',
            thicknessAssignment=FROM_SECTION
        )
        print("  [OK] Section assigned (full kwargs)")
    except (TypeError, Exception):
        # Fallback با kwargs حداقل
        try:
            part_to_use.SectionAssignment(
                region=coh_set,
                sectionName=cohesive_section_name
            )
            print("  [OK] Section assigned (minimal kwargs)")
        except Exception as e:
            print("  [ERROR] SectionAssignment failed: {}".format(e))
            print("  [INFO] Assign manually: Property > Section > Cohesive_Sec > Assign")

    # نکته: Material Orientation روی faces قبلاً در Stage 5 (build mode) اعمال شده.
    # چون از geometry استفاده می‌کنیم (نه orphan)، نیازی به اعمال دوباره روی elements نیست.

    print("")
    print("  [SUCCESS] Manual cohesive elements processed")
    return True


# ============================================================
# STAGE 12: ASSEMBLY + STEP + BC + JOB
# ============================================================

def setup_assembly_step_bc_job(model, layup, L, total_thickness, applied_strain_val,
                                job_name_str, auto_submit=False):
    """
    Stage 12: ساخت Assembly، Step، BC، و Job.

    این تابع بعد از Stage 11 (یا بعد از مُد build) فراخوانی می‌شه.

    کارها:
    1. ساخت Instance از part (Laminate)
    2. StaticStep با nlgeom=ON
    3. Field Output: S, E, U, RF, SDEG, STATUS, DMICRT
    4. BC: Fix_Left_X, Fix_Bottom_Y, Pull_Right_X (با edges)
    6. Job با numCpus و numDomains
    7. (اختیاری) submit و waitForCompletion
    """
    print("")
    print("=" * 70)
    print("Stage 12: Assembly + Step + BC + Job")
    print("=" * 70)

    assembly = model.rootAssembly
    instance_name = 'Laminate_Inst'

    # 1. تشخیص part برای instance (فقط geometry — orphan mesh حذف شد)
    if part_name not in model.parts.keys():
        print("  [ERROR] Part '{}' not found!".format(part_name))
        return False
    part_for_instance = model.parts[part_name]
    print("  [INFO] Using geometric part for instance: {}".format(part_name))

    # نکته: Material Orientation روی faces قبلاً در Stage 5 (build mode) اعمال شده.
    # چون از geometry استفاده می‌کنیم (نه orphan)، نیازی به اعمال دوباره روی elements نیست.

    # 2. ساخت Instance
    print("")
    print("  Creating instance...")
    if instance_name not in assembly.instances.keys():
        assembly.Instance(
            name=instance_name,
            part=part_for_instance,
            dependent=ON
        )
        print("  [OK] Instance '{}' created".format(instance_name))
    else:
        print("  [INFO] Instance '{}' already exists".format(instance_name))

    instance = assembly.instances[instance_name]

    # 4. StaticStep
    print("")
    print("  Creating StaticStep...")
    if 'Step-1' not in model.steps.keys():
        try:
            model.StaticStep(
                name='Step-1',
                previous='Initial',
                nlgeom=ON,
                initialInc=0.005,
                minInc=1.0e-12,
                maxInc=0.025,
                maxNumInc=10000
            )
            print("  [OK] StaticStep 'Step-1' created (nlgeom=ON, initialInc=0.005)")
        except (TypeError, Exception):
            try:
                model.StaticStep(name='Step-1', previous='Initial', nlgeom=ON)
                print("  [OK] StaticStep 'Step-1' created (minimal kwargs)")
            except Exception as e:
                print("  [ERROR] StaticStep creation failed: {}".format(e))
                return False
    else:
        print("  [INFO] Step-1 already exists")

    # 5. Field Output
    print("")
    print("  Configuring field output...")
    try:
        if 'F-Output-1' in model.fieldOutputRequests.keys():
            try:
                model.fieldOutputRequests['F-Output-1'].setValues(
                    variables=('S', 'E', 'U', 'RF', 'SDEG', 'STATUS', 'DMICRT'),
                    frequency=20
                )
                print("  [OK] Field output updated (frequency=20)")
            except (TypeError, Exception):
                try:
                    model.fieldOutputRequests['F-Output-1'].setValues(
                        variables=('S', 'E', 'U', 'RF', 'SDEG', 'STATUS', 'DMICRT')
                    )
                    print("  [OK] Field output updated (no frequency)")
                except Exception as e:
                    print("  [WARN] Could not update field output: {}".format(e))
        else:
            model.FieldOutputRequest(
                name='F-Output-1',
                createStepName='Step-1',
                variables=('S', 'E', 'U', 'RF', 'SDEG', 'STATUS', 'DMICRT'),
                frequency=20
            )
            print("  [OK] Field output created (frequency=20)")
    except Exception as e:
        print("  [WARN] Field output configuration failed: {}".format(e))

    # 6. BCs - استفاده از edges (چون geometry داریم، نه orphan)
    print("")
    print("  Creating boundary conditions...")
    tol = 1.0e-4

    # Left edges (x=0)
    left_edges = instance.edges.getByBoundingBox(
        xMin=-tol, yMin=-tol, zMin=-tol,
        xMax=tol, yMax=total_thickness + tol, zMax=tol
    )
    # Right edges (x=L)
    right_edges = instance.edges.getByBoundingBox(
        xMin=L - tol, yMin=-tol, zMin=-tol,
        xMax=L + tol, yMax=total_thickness + tol, zMax=tol
    )
    # Bottom edges (y=0)
    bottom_edges = instance.edges.getByBoundingBox(
        xMin=-tol, yMin=-tol, zMin=-tol,
        xMax=L + tol, yMax=tol, zMax=tol
    )

    print("    Left edges: {}".format(len(left_edges)))
    print("    Right edges: {}".format(len(right_edges)))
    print("    Bottom edges: {}".format(len(bottom_edges)))

    # حذف setهای قبلی اگر وجود دارن
    for set_name in ('Left_Edge', 'Right_Edge', 'Bottom_Edge'):
        if set_name in assembly.sets.keys():
            del assembly.sets[set_name]

    # ساخت setهای جدید با edges (مناسب geometry)
    left_set = assembly.Set(edges=left_edges, name='Left_Edge')
    right_set = assembly.Set(edges=right_edges, name='Right_Edge')
    bottom_set = assembly.Set(edges=bottom_edges, name='Bottom_Edge')

    # اعمال BCها
    if 'Fix_Left_X' not in model.boundaryConditions.keys():
        model.DisplacementBC(
            name='Fix_Left_X',
            createStepName='Step-1',
            region=left_set,
            u1=0.0
        )
        print("  [OK] BC 'Fix_Left_X' created (u1=0 on left)")

    if 'Fix_Bottom_Y' not in model.boundaryConditions.keys():
        model.DisplacementBC(
            name='Fix_Bottom_Y',
            createStepName='Step-1',
            region=bottom_set,
            u2=0.0
        )
        print("  [OK] BC 'Fix_Bottom_Y' created (u2=0 on bottom)")

    if 'Pull_Right_X' not in model.boundaryConditions.keys():
        pull_disp = applied_strain_val * L
        model.DisplacementBC(
            name='Pull_Right_X',
            createStepName='Step-1',
            region=right_set,
            u1=pull_disp
        )
        print("  [OK] BC 'Pull_Right_X' created (u1={} mm = {} strain)".format(
            pull_disp, applied_strain_val))

    # 7. Job
    print("")
    print("  Creating job...")
    if job_name_str not in mdb.jobs.keys():
        mdb.Job(
            name=job_name_str,
            model=model_name,
            description='Mesoscale transverse cracking simulation',
            numCpus=job_cpus,
            numDomains=job_domains
        )
        print("  [OK] Job '{}' created (cpus={}, domains={})".format(
            job_name_str, job_cpus, job_domains))
    else:
        print("  [INFO] Job '{}' already exists".format(job_name_str))

    # 8. Submit (اختیاری)
    if auto_submit:
        print("")
        print("  Submitting job...")
        try:
            mdb.jobs[job_name_str].submit(consistencyChecking=OFF)
            mdb.jobs[job_name_str].waitForCompletion()
            print("  [OK] Job '{}' completed".format(job_name_str))
        except Exception as e:
            print("  [ERROR] Job submission failed: {}".format(e))
            print("  [INFO] You can submit manually from Job Manager")

    print("")
    print("=" * 70)
    print("  [SUCCESS] Assembly, Step, BCs, and Job all configured")
    print("=" * 70)
    return True


# ============================================================
# PRINT FINAL SUMMARY
# ============================================================

def print_summary(p, layup, n_cohesive, n_cells_thickness):
    """نمایش خلاصه نهایی پارت."""
    print("")
    print("=" * 70)
    print("PARTITIONING + MATERIALS COMPLETE - 2D Model")
    print("=" * 70)
    print("Part name: {}".format(p.name))
    print("Total faces:    {:4d}".format(len(p.faces)))
    print("Total edges:    {:4d}".format(len(p.edges)))
    print("Total vertices: {:4d}".format(len(p.vertices)))
    print("Total datums:   {:4d}".format(len(p.datums)))

    n_plies = len(layup)
    n_90_plies = 0
    n_0_plies = 0
    for item in layup:
        if item[0] == 90:
            n_90_plies += 1
        elif item[0] == 0:
            n_0_plies += 1
    print("")
    print("Layup: {} plies ({} x 0 deg + {} x 90 deg)".format(
        n_plies, n_0_plies, n_90_plies))
    print("  90 sub-cells through thickness: {} per ply".format(n_cells_thickness))
    print("  Cohesive columns along length: {}".format(n_cohesive))
    print("  Analysis type: 2D {}".format(analysis_type))

    # خلاصه setها
    set_names = sorted(p.sets.keys())
    print("")
    print("Sets in part ({} total):".format(len(set_names)))
    for sname in set_names:
        s = p.sets[sname]
        n_faces = len(s.faces) if hasattr(s, 'faces') else 0
        n_edges = len(s.edges) if hasattr(s, 'edges') else 0
        if n_faces > 0:
            print("  - {} ({} faces)".format(sname, n_faces))
        elif n_edges > 0:
            print("  - {} ({} edges)".format(sname, n_edges))
        else:
            print("  - {} (empty)".format(sname))

    print("")
    print("=" * 70)
    print("NEXT STEPS - 2D Analysis")
    print("=" * 70)
    print("1. Insert cohesive elements:")
    print("   - Use 'Insert cohesive seams' tool with Potential_Crack_Edges set")
    print("   - Element type: COH2D4")
    print("2. Mesh the part:")
    if analysis_type == 'PLANE_STRAIN':
        print("   - Element type: CPE4R (4-node plane strain quadrilateral)")
    else:
        print("   - Element type: CPS4R (4-node plane stress quadrilateral)")
    print("3. Apply boundary conditions and loads")
    print("4. Submit job and post-process")
    print("=" * 70)


# ============================================================
# MAIN SCRIPT
# ============================================================

def main():
    """
    تابع اصلی - دو مُد اجرا:

    مُد 'build' (پیش‌فرض):
      Stage 1:  ساخت هندسه پایه 2D
      Stage 2:  پارتیشن‌بندی با Sketch
      Stage 3:  ساخت face sets (Ply_0_Set, Set_90deg_Vf_*, Potential_Crack_Edges)
      Stage 4:  ساخت متریال‌ها و sectionهای continuum
      Stage 4.5: ساخت cohesive material + section (با Initial thickness=Specify, Viscosity)
      Stage 5:  Material Orientation روی faces (GLOBAL, AXIS_3)
      Stage 6:  Mesh generation (CPE4R یا CPS4R)
      Stage 7:  ذخیره .cae
      [متوقف — کاربر در CAE دستی cohesive درج می‌کنه]

    مُد 'resume':
      Stage 11: پردازش CohesiveSeam-*-Elements (force COH2D4 + SectionAssignment)
      Stage 12: Assembly + Step + BC + Job (با edges به‌جای nodes)
      (اختیاری: submit و waitForCompletion)

    نکته مهم درباره Element Controls (Viscosity):
      - Cohesive_Sec با Initial thickness=Specify (0.001) و response=TRACTION_SEPARATION ساخته می‌شه
      - Viscosity=1e-4 از طریق Section Controls (Element Controls در UI) اضافه می‌شه
      - اگر API شکست بخوره، راهنمای Keyword Editor چاپ می‌شه (مرحلهٔ دستی)
      - Viscosity برای convergence در crack initiation حیاتی است

    نکته درباره Orphan Mesh:
      - حذف شد چون برای مدل ما فایده‌ای نداشت
      - ابزار 'Insert cohesive seams' روی geometry کار می‌کنه
      - Instance مستقیماً از part اصلی ساخته می‌شه
      - BCs با edges (نه nodes) تعریف می‌شن
    """

    print("")
    print("#" * 70)
    print("# ABAQUS SCRIPT: Stochastic Mesoscale Laminate (2D)")
    print("# Article: Transverse Crack Multiplication in Thin-Ply Laminates")
    print("# Analysis: 2D Cross-section (X-Y plane)")
    print("# Python 2.7 Compatible")
    print("# Run mode: {}".format(run_mode))
    print("#" * 70)

    # ============================================================
    # اعمال پروفایل job فعال (override پارامترهای هندسی)
    # ============================================================
    if not apply_job_profile():
        return

    # ============================================================
    # مُد RESUME - بعد از درج دستی cohesive
    # ============================================================
    if run_mode == 'resume':
        print("")
        print("=" * 70)
        print("RESUME MODE - Processing manual cohesive elements + creating job")
        print("=" * 70)

        model = mdb.models[model_name]
        if part_name not in model.parts.keys():
            print("[ERROR] Part '{}' not found! Did you run 'build' mode first?".format(part_name))
            return
        p = model.parts[part_name]

        # محاسبه layup برای total_thickness
        layup = build_layup(layup_type, n90, t0, t90)
        total_thickness = 0.0
        for item in layup:
            total_thickness += item[1]

        # Stage 11: پردازش CohesiveSeam-*-Elements
        success = process_manual_cohesive(model, p)
        if not success:
            print("")
            print("[WARN] Stage 11 had issues. Continuing to Stage 12 anyway...")

        # Stage 12: Assembly + Step + BC + Job
        setup_assembly_step_bc_job(
            model=model,
            layup=layup,
            L=L,
            total_thickness=total_thickness,
            applied_strain_val=applied_strain,
            job_name_str=job_name,
            auto_submit=auto_submit_job
        )

        # ذخیره نهایی
        save_cae()

        print("")
        print("[SUCCESS] Resume mode completed!")
        if not auto_submit_job:
            print("[INFO] Job '{}' is ready. Submit manually from Job Manager.".format(job_name))
        return

    # ============================================================
    # مُد BUILD - اجرای کامل از ابتدا
    # ============================================================
    print("")
    print("=" * 70)
    print("BUILD MODE - Creating geometry, partitions, materials, mesh")
    print("=" * 70)

    # چاپ جدول interpolation داینامیک برای شفافیت
    print_interpolation_table(VF_LEVELS, units='MPa')

    # مرحله 0: ساخت لایه‌چینی
    layup = build_layup(layup_type, n90, t0, t90)
    print_layup_info(layup, t0, t90, n90, layup_type)

    # محاسبه ضخامت کل
    total_thickness = 0.0
    for item in layup:
        total_thickness += item[1]

    # مرحله 1: ساخت هندسه پایه 2D
    print(">>> Stage 1: Creating 2D base geometry...")
    p = create_base_geometry_2d(model_name, part_name, L, total_thickness)

    # دریافت مدل
    model = mdb.models[model_name]

    # مرحله 2: پارتیشن‌بندی با Sketch (روش اثبات‌شده)
    print(">>> Stage 2: Partitioning with Sketch method...")
    n_cohesive = partition_with_sketch(p, model, L, total_thickness, layup,
                                       n_cells_thickness, L_gauge, rho)

    # مرحله 3: ساخت face sets
    print(">>> Stage 3: Creating face sets...")
    create_face_sets(p, layup, L, n_cells_thickness)

    # مرحله 4: ساخت متریال‌ها و sectionهای continuum
    print(">>> Stage 4: Creating continuum materials + sections + assignments...")
    build_materials_and_sections(p, model, layup)

    # مرحله 4.5: ساخت cohesive material + section (آماده برای استفاده بعد از manual insertion)
    print(">>> Stage 4.5: Creating cohesive material + section (for later use)...")
    build_cohesive_material_and_section(model)

    # مرحله 5: اختصاص Material Orientation روی faces
    print(">>> Stage 5: Assigning Material Orientation...")
    assign_material_orientation(p)

    # مرحله 6: Mesh generation
    print(">>> Stage 6: Generating mesh...")
    mesh_ok = generate_mesh(p, model)
    if not mesh_ok:
        print("[ERROR] Mesh generation failed. Stopping.")
        return

    # نکته: مرحلهٔ Orphan Mesh حذف شد. ابزار 'Insert cohesive seams' روی
    # هندسه (geometry) کار می‌کنه و Instance مستقیماً از part اصلی ساخته می‌شه.

    # مرحله 7: ذخیره .cae
    print(">>> Stage 7: Saving .cae...")
    save_cae()

    # مرحله 8: خلاصه نهایی
    print_summary(p, layup, n_cohesive, n_cells_thickness)

    # ============================================================
    # دستورالعمل کارهای دستی
    # ============================================================
    print("")
    print("=" * 70)
    print("MANUAL STEPS REQUIRED - کارهای دستی لازم")
    print("=" * 70)
    print("")
    print("Phase A: Insert Cohesive Elements (در CAE)")
    print("-" * 70)
    print("  1. Open CAE with the saved .cae file:")
    print("     abaqus cae database={}.cae".format(model_name))
    print("")
    print("  2. Switch to Mesh module")
    print("")
    print("  3. Menu: Mesh -> Edit...")
    print("     - Category: Mesh")
    print("     - Method: Insert cohesive seams")
    print("")
    print("  4. Select the part: {}".format(part_name))
    print("")
    print("  5. Click 'Sets...' and select: Potential_Crack_Edges")
    print("     (should contain ~{} vertical edges)".format(
        n_cohesive * 2 * n_cells_thickness if layup_type == 'symmetric'
        else n_cohesive * n_cells_thickness))
    print("")
    print("  6. Click 'Done' - Abaqus creates 'CohesiveSeam-1-Elements' set")
    print("     (with ~{} COH2D4 elements)".format(
        n_cohesive * 2 * n_cells_thickness if layup_type == 'symmetric'
        else n_cohesive * n_cells_thickness))
    print("")
    print("  7. Save the file: Ctrl+S")
    print("")
    print("-" * 70)
    print("Phase B: Resume Script (ترمینال)")
    print("-" * 70)
    print("  8. Edit this script: change 'run_mode = \"build\"' to 'run_mode = \"resume\"'")
    print("     (line ~108 in the script)")
    print("")
    print("  9. Re-run the script:")
    print("     abaqus cae noGUI=abaqus_laminate_partitioning.py")
    print("")
    print("  This will:")
    print("    - Process CohesiveSeam-1-Elements (force COH2D4 + assign Cohesive_Sec)")
    print("    - Create Assembly + Step + BC + Job")
    print("    - Save the .cae again")
    print("")
    print("-" * 70)
    print("Phase C: Submit Job (اختیاری)")
    print("-" * 70)
    print("  10. Either:")
    print("      a) Set 'auto_submit_job = True' in the script and re-run resume mode, OR")
    print("      b) In CAE: Job Manager -> select '{}' -> Submit".format(job_name))
    print("")
    print("=" * 70)
    print("[SUCCESS] Build mode completed! Now follow the manual steps above.")
    print("=" * 70)


# ============================================================
# RUN
# ============================================================

if __name__ == '__main__':
    main()
