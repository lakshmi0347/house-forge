"""
House-Forge Construction Estimation Service
============================================
Full rewrite to match all fields in create_project.html:
  - Residential / Villa / Apartment modes
  - Structural: concrete grade, steel grade, slab thickness, soil, foundation, waterproofing
  - Masonry: wall material, thickness, doors/windows, internal + external plaster
  - Finishing: flooring, bathroom tiles, internal/external paint, false ceiling, kitchen
  - Add-ons: car porch, garden, boundary wall, water sump/tank, anti-termite
  - Plumbing: pipe material, taps, showers, geysers, sanitary grade
  - Electrical: switchboards, AC points, wiring type, inverter, earthing
  - Villa extras: pool, staircase style, cladding, landscaping, driveway
  - Apartment: BHK mix, floors, unit finishes, parking, lifts, safety systems
  - Estimate scope: material_only vs material_and_labour
  - AI fallback: calls Anthropic API when exact fields are ambiguous
"""

import math
from typing import Optional

# ─────────────────────────────────────────────────────────────────
#  RATE TABLES  (all ₹/sqft of built-up area unless noted)
# ─────────────────────────────────────────────────────────────────

# Concrete grade → extra cost multiplier on structural stages
CONCRETE_GRADE_FACTOR = {"M20": 1.00, "M25": 1.08, "M30": 1.16, "M35": 1.25, "M40": 1.35}

# Steel grade → cost multiplier (material only)
STEEL_GRADE_FACTOR = {"Fe500": 1.00, "Fe550": 1.06, "Fe500D": 1.04}

# Slab thickness (inches) → concrete volume multiplier
SLAB_THICKNESS_FACTOR = {4.5: 0.90, 5: 1.00, 5.5: 1.10, 6: 1.20}

# Foundation type → base excavation + concrete cost per sqft plot area
FOUNDATION_RATE = {
    "isolated":  {"rate_per_sqft_bua": 220, "depth_factor": 1.0},
    "strip":     {"rate_per_sqft_bua": 260, "depth_factor": 1.1},
    "raft":      {"rate_per_sqft_bua": 340, "depth_factor": 1.25},
    "pile":      {"rate_per_sqft_bua": 520, "depth_factor": 1.60},
    "combined":  {"rate_per_sqft_bua": 300, "depth_factor": 1.15},
}

# Soil condition → depth multiplier already factored into foundation choice;
# we add an extra site-work cost per sqft BUA
SOIL_EXTRA_RATE = {
    "hard_rock": 0, "firm_soil": 0, "soft_soil": 40,
    "marshy": 120, "filled": 80
}

# Wall material ₹/brick-equivalent quantity cost per sqft of wall area
WALL_MATERIAL_RATE = {
    "red_clay":  {"mat_rate": 6.5,  "bags_per_sqft": 0.30},
    "aac_blocks":{"mat_rate": 9.0,  "bags_per_sqft": 0.22},
    "fly_ash":   {"mat_rate": 7.5,  "bags_per_sqft": 0.26},
    "hollow_concrete": {"mat_rate": 7.0, "bags_per_sqft": 0.24},
}

# Plaster type → ₹/sqft of plastered area
PLASTER_RATE = {
    "12mm_cm":       18,  "20mm_cm":       22,
    "gypsum":        28,  "skim_coat":     14,
    "12mm_cm_15":    20,  "20mm_cm_14":    24,
    "textured_coat": 35,  "none":           0,
    "drywall":       45,
}

# Door material → ₹ per door (supply only)
DOOR_RATE = {
    "flush_hollow":   9000,  "flush_solid":    22000,
    "panel_teak":    45000,  "upvc_door":      25000,
    "aluminium_door":30000,  "designer_wood":  90000,
}

# Window material → ₹ per window
WINDOW_RATE = {
    "ms_grill":         5500,  "aluminium_sliding": 13000,
    "upvc_casement":   22000,  "upvc_sliding":      17000,
    "wooden_frame":    30000,
}

# Flooring → ₹/sqft
FLOORING_RATE = {
    "vitrified":       90, "marble":          250,
    "granite":         200,"hardwood":        350,
    "ceramic":          60,"italian_marble":  580,
    "premium_granite": 300,"natural_stone":   380,
}

# Bathroom wall tile → ₹/sqft
BATH_TILE_RATE = {
    "ceramic_economy":  45,  "ceramic_standard": 80,
    "vitrified_wall":  115,  "designer_tiles":   250,
    "natural_stone_bath": 375,
}

# Paint → ₹/sqft of wall area
INTERNAL_PAINT_RATE = {
    "emulsion": 23, "luxury": 37, "texture": 70,
}
EXTERNAL_PAINT_RATE = {
    "weathershield": 28, "elastomeric": 46, "texture_ext": 78,
}

# False ceiling gypsum → ₹/sqft
FALSE_CEILING_RATE = 85   # per sqft

# Kitchen type → ₹/linear-ft of platform
KITCHEN_PLATFORM_RATE = {
    "semi_modular": 0,   # included in carpentry base
    "modular":      3500  # per linear ft extra
}
KITCHEN_STONE_RATE = {
    "granite_standard": 220, "granite_premium":  450,
    "quartz":           650, "marble_kitchen":   375,
    "ceramic_tiles":     90,
}

# Pipe material → ₹/rft installed
PIPE_RATE = {
    "cpvc": 150, "upvc": 80, "ppr": 140, "gi": 180,
}

# Sanitary ware → ₹/bathroom set (supply)
SANITARY_RATE = {
    "standard": 11500, "mid": 26500, "premium": 60000, "luxury": 100000,
}

# Wiring → ₹/rft installed
WIRING_RATE = {
    "fr_pvc": 30, "lszh": 48, "armoured": 65,
}

# Earthing → ₹/point
EARTHING_RATE = {
    "plate": 6000, "pipe": 4500, "chemical": 12000,
}

# Waterproofing → ₹/sqft of treated area
WATERPROOFING_RATE = {
    "brick_bat_coba": 42,  "chemical_coat":  28,
    "membrane":       65,  "crystalline":    100,
    "none":            0,
}

# Anti-termite → ₹/sqft of plot area
ANTI_TERMITE_RATE = {
    "pre_construction": 11.5,
    "post_construction": 8.0,
    "none": 0,
}

# Pool finish → ₹/sqft of pool surface
POOL_FINISH_RATE = {
    "ceramic_tile": 115,  "vitrified_tile":   200,
    "glass_mosaic": 475,  "fibreglass":       550,
    "exposed_aggregate": 275,
}

# Landscaping → ₹/sqft
LANDSCAPING_RATE = {
    "basic": 60, "standard": 115, "premium": 225, "luxury": 450,
}

# Cladding → ₹/sqft of external wall area
CLADDING_RATE = {
    "plaster": 0,   # covered in external plaster
    "stone": 425,   "glass_facade": 1650,
    "composite": 325,
}

# Façade (apartment) → ₹/sqft
FACADE_RATE = {
    "plaster_paint":  100, "texture_paint":  150,
    "acp_cladding":   325, "stone_cladding": 425,
    "glass_curtain": 1200,
}


# ─────────────────────────────────────────────────────────────────
#  HELPER: build wall area  (both internal + external)
# ─────────────────────────────────────────────────────────────────

def _wall_areas(sqft: float, floors: int, ceiling_ht: float,
                num_doors: int, num_windows: int,
                outer_wall_ratio: float = 0.45) -> dict:
    """
    Rough wall area split.
    outer_wall_ratio: fraction of total wall perimeter that is external.
    Door void: 3×7 ft = 21 sqft. Window void: 4×4 = 16 sqft.
    Returns gross (before void deduction) and net areas.
    """
    # Estimate perimeter from sqft: assume square floor plan
    side = math.sqrt(sqft / floors)
    perimeter = 4 * side  # rough

    ext_wall_area_gross = perimeter * ceiling_ht * floors
    int_wall_area_gross = ext_wall_area_gross * (1 - outer_wall_ratio) / outer_wall_ratio

    door_void  = num_doors   * 21  # sqft
    win_void   = num_windows * 16  # sqft
    total_void = door_void + win_void

    ext_wall_net = max(0, ext_wall_area_gross - total_void * outer_wall_ratio)
    int_wall_net = max(0, int_wall_area_gross - total_void * (1 - outer_wall_ratio))

    return {
        "ext_gross": ext_wall_area_gross,
        "int_gross": int_wall_area_gross,
        "ext_net":   ext_wall_net,
        "int_net":   int_wall_net,
        "total_gross": ext_wall_area_gross + int_wall_area_gross,
    }


def _false_ceiling_area(sqft: float, coverage: str) -> float:
    if coverage in ("no", "none", None):
        return 0
    if coverage == "partial":
        return sqft * 0.35
    if coverage == "full":
        return sqft * 1.0
    return 0


# ─────────────────────────────────────────────────────────────────
#  RESIDENTIAL / VILLA CORE CALCULATOR
# ─────────────────────────────────────────────────────────────────

def _calc_residential(form: dict, sqft: float, plot_area: float,
                      floors: int, bathrooms: int, rooms: int,
                      ceiling_ht: float, prefix: str = "") -> dict:
    """
    Returns a stage_breakdown dict with ₹ costs for each section.
    prefix = "" for residential, "villa_" for villa fields.
    """
    p = prefix  # shorthand

    def f(key, default=None):
        return form.get(f"{p}{key}", form.get(key, default))

    # ── Material grade multipliers ──
    conc_fac  = CONCRETE_GRADE_FACTOR.get(f("concrete_grade", "M20"), 1.0)
    steel_fac = STEEL_GRADE_FACTOR.get(f("steel_grade", "Fe500"), 1.0)
    slab_fac  = SLAB_THICKNESS_FACTOR.get(float(f("slab_thickness", 5)), 1.0)

    # ── 1. FOUNDATION ──
    fd_type   = f("foundation_type", "isolated")
    fd_depth  = float(f("foundation_depth", 6))
    soil_type = f("soil_condition", "firm_soil")
    fd_info   = FOUNDATION_RATE.get(fd_type, FOUNDATION_RATE["isolated"])
    fd_rate   = fd_info["rate_per_sqft_bua"] * (fd_depth / 6) * conc_fac * slab_fac
    soil_extra= SOIL_EXTRA_RATE.get(soil_type, 0)
    anti_t    = ANTI_TERMITE_RATE.get(f("anti_termite", "pre_construction"), 11.5)
    wproof    = WATERPROOFING_RATE.get(f("roof_waterproofing", "brick_bat_coba"), 42)

    foundation_cost = (fd_rate * sqft) + (soil_extra * sqft) + (anti_t * plot_area) + (wproof * (sqft / floors))

    # ── 2. WALLS (MASONRY) ──
    num_doors   = int(f("num_doors",    6))
    num_windows = int(f("num_windows",  8))
    wall_mat    = f("wall_material", "red_clay")
    wm          = WALL_MATERIAL_RATE.get(wall_mat, WALL_MATERIAL_RATE["red_clay"])
    wall_info   = _wall_areas(sqft, floors, ceiling_ht, num_doors, num_windows)

    outer_thick = float(f("wall_thickness", 9)) / 9   # normalised against 9-inch
    inner_thick = float(f("inner_wall_thickness", 4.5)) / 9

    masonry_mat_cost = (wall_info["ext_net"] * wm["mat_rate"] * outer_thick +
                        wall_info["int_net"] * wm["mat_rate"] * inner_thick)

    int_plaster  = PLASTER_RATE.get(f("plaster_type", "12mm_cm"), 18)
    ext_plaster  = PLASTER_RATE.get(f("external_plaster_type", "12mm_cm_15"), 20)
    plaster_cost = (wall_info["int_net"] * int_plaster +
                    wall_info["ext_net"] * ext_plaster)

    door_mat  = f("door_material", "flush_hollow")
    win_mat   = f("window_material", "aluminium_sliding")
    openings_cost = (DOOR_RATE.get(door_mat, 9000) * num_doors +
                     WINDOW_RATE.get(win_mat, 13000) * num_windows)

    walls_cost = masonry_mat_cost + plaster_cost + openings_cost

    # ── 3. FLOORING & SLAB ──
    floor_type   = f("flooring_type", "vitrified")
    floor_rate   = FLOORING_RATE.get(floor_type, 90)
    slab_concrete= sqft * floors * 180 * conc_fac * slab_fac  # ₹/sqft slab
    steel_cost   = sqft * floors * 3.5 * 65 * steel_fac        # 3.5 kg/sqft × ₹65/kg

    bath_tile     = f("bathroom_wall_tile", "ceramic_standard")
    bath_tile_rate= BATH_TILE_RATE.get(bath_tile, 80)
    bath_wall_area= bathrooms * 7 * (ceiling_ht * 0.65)  # dado ht ~65% ceiling ht
    bath_tile_cost= bath_wall_area * bath_tile_rate

    flooring_cost = (sqft * floors * floor_rate) + slab_concrete + steel_cost + bath_tile_cost

    # ── 4. ROOFING ──
    roof_type = f("roof_type", "flat_rcc")
    roof_mult = 1.0
    if prefix == "villa_":
        roof_type = f("roof_type", "flat_rcc")
        if roof_type == "sloped_tiled":
            roof_mult = 1.15
    roofing_cost = sqft * 190 * conc_fac * slab_fac * roof_mult

    # Staircase
    stair_type = f("staircase_type", "rcc")
    if prefix == "villa_":
        stair_type = f("staircase", "standard")
    stair_cost = 0
    if stair_type not in ("none", None):
        stair_cost_map = {
            "rcc": 60000, "standard": 60000, "spiral": 180000,
            "grand_marble": 450000, "steel_glass": 250000, "wooden": 200000,
        }
        stair_cost = stair_cost_map.get(stair_type, 60000) * max(1, floors - 1)

    roofing_cost += stair_cost

    # ── 5. PLUMBING ──
    pipe_mat     = f("pipe_material", "cpvc")
    pipe_rate    = PIPE_RATE.get(pipe_mat, 150)
    total_pipe   = (bathrooms * 22) + (floors * 50) + 30   # rft
    pipe_cost    = total_pipe * pipe_rate

    num_taps     = int(f("num_taps",     bathrooms * 4 + 4))
    num_showers  = int(f("num_showers",  bathrooms))
    num_geysers  = int(f("num_geysers",  bathrooms))
    san_grade    = f("sanitary_grade", "standard")
    san_rate     = SANITARY_RATE.get(san_grade, 11500)

    shower_cost  = num_showers * 5500
    geyser_cost  = num_geysers * 2200  # plumbing point cost (not fixture)
    tap_cost     = num_taps    * 850

    # Sump/overhead tank
    sump_cost    = 35000  # default standard sump
    tank_cost    = 4500   # 1000L overhead tank

    plumbing_cost = pipe_cost + san_rate * bathrooms + shower_cost + geyser_cost + tap_cost + sump_cost + tank_cost

    # ── 6. ELECTRICAL ──
    num_sw  = int(f("num_switchboards", rooms * 2 + bathrooms + 3))
    num_ac  = int(f("num_ac_points",    0))
    wiring  = f("wiring_type",          "fr_pvc")
    inv     = f("inverter_wiring",      "none")
    earth   = f("earthing_system",      "plate")

    wire_rft  = sqft * floors * 2.5
    wire_cost = wire_rft * WIRING_RATE.get(wiring, 30)
    sw_cost   = num_sw * 1800
    ac_cost   = num_ac * 4500
    earth_cost= EARTHING_RATE.get(earth, 6000)
    inv_cost  = {"none": 0, "partial": 15000, "full": 45000}.get(inv, 0)

    electrical_cost = wire_cost + sw_cost + ac_cost + earth_cost + inv_cost

    # ── 7. FINISHING (paint + false ceiling) ──
    int_paint   = f("internal_paint_quality", "emulsion")
    ext_paint   = f("external_paint_quality", "weathershield")
    int_p_rate  = INTERNAL_PAINT_RATE.get(int_paint, 23)
    ext_p_rate  = EXTERNAL_PAINT_RATE.get(ext_paint, 28)

    putty_rate  = 18   # ₹/sqft internal wall
    int_paint_cost = wall_info["int_net"] * (putty_rate + int_p_rate)
    ext_paint_cost = wall_info["ext_net"] * ext_p_rate

    fc_key  = f("false_ceiling_yn", "no")
    if prefix == "villa_":
        fc_key = f("false_ceiling", "no")
    fc_area = _false_ceiling_area(sqft, fc_key)
    fc_cost = fc_area * FALSE_CEILING_RATE

    finishing_cost = int_paint_cost + ext_paint_cost + fc_cost

    # ── 8. CARPENTRY & KITCHEN ──
    kt_type   = f("kitchen_type", "semi_modular")
    kp_length = float(f("kitchen_platform_length", 10) or 10)
    kp_stone  = f("kitchen_platform_stone", "granite_standard")
    kp_rate   = KITCHEN_STONE_RATE.get(kp_stone, 220)
    kp_area   = kp_length * 2.5   # sqft of slab

    modular_extra = KITCHEN_PLATFORM_RATE.get(kt_type, 0) * kp_length
    kp_cost   = kp_area * kp_rate + modular_extra

    # Base carpentry (wardrobes, misc joinery)
    base_carpentry = sqft * 55 * (1.5 if prefix == "villa_" else 1.0)
    carpentry_cost = base_carpentry + kp_cost

    # ── 9. EXTERNAL FEATURES ──
    exterior_cost = 0

    # Car porch
    porch_key = f"{p}car_porch_size" if prefix == "villa_" else "car_porch_size"
    porch_sz  = form.get(porch_key, "single")
    porch_sqft_map = {"single": 200, "double": 400, "triple": 600}
    porch_sqft = float(form.get(f"{p}car_porch_sqft") or porch_sqft_map.get(porch_sz, 200))
    # Car porch included only if tile-active — for residential default True
    exterior_cost += porch_sqft * 850   # ₹850/sqft covered area

    # Garden
    garden_sqft = float(f("garden_sqft") or 0)
    if garden_sqft:
        exterior_cost += garden_sqft * 60

    # Boundary wall
    bw_rft    = float(f("boundary_rft") or 0)
    bw_height = float(f("boundary_height", 6))
    bw_finish = f("boundary_finish", "plaster")
    bw_finish_rate = {"plaster": 180, "exposed": 120, "cladding": 320,
                      "stone_cladding": 380, "composite_cladding": 290}.get(bw_finish, 180)
    exterior_cost += bw_rft * bw_height * bw_finish_rate

    # Water sump (already in plumbing; gate if boundary present)
    if bw_rft:
        gate_rate = {"ms_fabricated": 45000, "sliding_auto": 115000,
                     "swing_ornamental": 90000, "ss_glass": 185000}
        gate_key  = f("{p}gate_type") if prefix == "villa_" else "gate_type"
        gate_cost = gate_rate.get(form.get(gate_key, "ms_fabricated"), 45000)
        exterior_cost += gate_cost

    # ── Villa-specific extras ──
    villa_extra = 0
    if prefix == "villa_":
        # Cladding
        cladding = form.get("villa_cladding", "plaster")
        clad_rate = CLADDING_RATE.get(cladding, 0)
        villa_extra += wall_info["ext_net"] * clad_rate

        # Pool
        pl = float(form.get("pool_length") or 0)
        pw = float(form.get("pool_width") or 0)
        pd = float(form.get("pool_depth", 5) or 5)
        if pl and pw:
            pool_surface = 2*(pl*pd + pw*pd) + pl*pw
            pool_fin     = POOL_FINISH_RATE.get(form.get("pool_finish", "vitrified_tile"), 200)
            pool_shell   = pl * pw * pd * 0.4 * 8000  # rough shell ₹
            villa_extra += pool_surface * pool_fin + pool_shell

        # Landscaping
        vg_sqft = float(form.get("villa_garden_sqft") or 0)
        vl_grade= form.get("villa_landscaping_grade", "standard")
        villa_extra += vg_sqft * LANDSCAPING_RATE.get(vl_grade, 115)

        # Driveway
        vd_sqft = float(form.get("villa_driveway_sqft") or 0)
        vd_fin  = {"interlocking_pavers": 180, "natural_stone_path": 380,
                   "stamped_concrete": 220, "granite_cobble": 420}.get(
                   form.get("villa_driveway_finish", "interlocking_pavers"), 180)
        villa_extra += vd_sqft * vd_fin

    exterior_cost += villa_extra

    # ── 10. MISCELLANEOUS (contingency, temp works, safety) ──
    misc_cost = sqft * floors * 35

    stage_breakdown = {
        "foundation":    round(foundation_cost, 0),
        "walls":         round(walls_cost, 0),
        "flooring":      round(flooring_cost, 0),
        "roofing":       round(roofing_cost, 0),
        "plumbing":      round(plumbing_cost, 0),
        "electrical":    round(electrical_cost, 0),
        "finishing":     round(finishing_cost, 0),
        "carpentry":     round(carpentry_cost, 0),
        "exterior":      round(exterior_cost, 0),
        "miscellaneous": round(misc_cost, 0),
    }
    return stage_breakdown


# ─────────────────────────────────────────────────────────────────
#  APARTMENT CALCULATOR
# ─────────────────────────────────────────────────────────────────

def _calc_apartment(form: dict, sqft: float, plot_area: float, floors: int) -> dict:
    bhk1_count = int(form.get("apt_1bhk_count") or 0)
    bhk2_count = int(form.get("apt_2bhk_count") or 0)
    bhk3_count = int(form.get("apt_3bhk_count") or 0)
    total_units = int(form.get("apt_total_units") or max(bhk1_count+bhk2_count+bhk3_count, 1))
    total_baths = bhk1_count*1 + bhk2_count*2 + bhk3_count*3 or total_units * 2

    bhk1_size = float(form.get("apt_1bhk_size") or 550)
    bhk2_size = float(form.get("apt_2bhk_size") or 950)
    bhk3_size = float(form.get("apt_3bhk_size") or 1400)

    ceiling_ht = float(form.get("apt_ceiling_height") or 10)
    ca_pct     = float(form.get("apt_common_area_pct") or 20) / 100

    conc_fac   = CONCRETE_GRADE_FACTOR.get(form.get("apt_concrete_grade", "M30"), 1.16)
    steel_fac  = STEEL_GRADE_FACTOR.get(form.get("apt_steel_grade", "Fe500D"), 1.04)
    slab_fac   = SLAB_THICKNESS_FACTOR.get(float(form.get("apt_slab_thickness") or 5), 1.0)

    # ── Foundation ──
    fd_type  = form.get("apt_foundation_type", "raft")
    fd_depth = float(form.get("apt_foundation_depth") or 8)
    soil     = form.get("apt_soil_condition", "firm_soil")
    fd_info  = FOUNDATION_RATE.get(fd_type, FOUNDATION_RATE["raft"])
    fd_cost  = fd_info["rate_per_sqft_bua"] * (fd_depth/8) * conc_fac * slab_fac * sqft
    soil_ex  = SOIL_EXTRA_RATE.get(soil, 0) * sqft
    anti_t   = ANTI_TERMITE_RATE.get(form.get("apt_anti_termite", "pre_construction"), 11.5) * plot_area
    wproof   = WATERPROOFING_RATE.get(form.get("apt_roof_waterproofing", "membrane"), 65) * (sqft/floors)
    foundation_cost = fd_cost + soil_ex + anti_t + wproof

    # Basement extras
    park_type = form.get("apt_parking_type", "open")
    basement_cost = 0
    if park_type.startswith("basement"):
        b_depth   = float(form.get("apt_basement_depth") or 14)
        b_levels  = 2 if park_type == "basement_2" else 1
        bw_rate   = WATERPROOFING_RATE.get(form.get("apt_basement_waterproofing", "membrane"), 65)
        basement_cost = sqft * b_depth * 0.15 * conc_fac * b_levels + (sqft * bw_rate * 0.4 * b_levels)

    foundation_cost += basement_cost

    # ── Structure (walls + slabs, repeated across all floors) ──
    wall_mat   = form.get("apt_wall_material", "aac_blocks")
    wm         = WALL_MATERIAL_RATE.get(wall_mat, WALL_MATERIAL_RATE["aac_blocks"])
    num_doors  = (bhk1_count*3 + bhk2_count*5 + bhk3_count*7) or total_units*4
    num_windows= (bhk1_count*4 + bhk2_count*6 + bhk3_count*8) or total_units*6

    wall_info  = _wall_areas(sqft, floors, ceiling_ht, num_doors, num_windows)
    outer_thick= float(form.get("apt_wall_thickness", 9)) / 9
    masonry    = wall_info["ext_net"] * wm["mat_rate"] * outer_thick + wall_info["int_net"] * wm["mat_rate"] * 0.5

    int_plaster = PLASTER_RATE.get(form.get("apt_internal_plaster", "gypsum"), 28)
    ext_plaster = PLASTER_RATE.get(form.get("apt_external_plaster", "12mm_cm_15"), 20)
    plaster     = wall_info["int_net"] * int_plaster + wall_info["ext_net"] * ext_plaster

    door_mat  = form.get("apt_door_material", "flush_solid")
    win_mat   = form.get("apt_window_material", "aluminium_sliding")
    openings  = DOOR_RATE.get(door_mat, 22000)*num_doors + WINDOW_RATE.get(win_mat, 13000)*num_windows

    # Façade (external)
    facade_type = form.get("apt_facade_type", "plaster_paint")
    facade_rate = FACADE_RATE.get(facade_type, 100)
    facade_cost = wall_info["ext_net"] * facade_rate
    ext_paint   = EXTERNAL_PAINT_RATE.get(form.get("apt_external_paint", "weathershield"), 28)
    facade_cost += wall_info["ext_net"] * ext_paint

    # Staircases
    num_stairs  = int(form.get("apt_staircases") or 2)
    stair_type  = form.get("apt_staircase_type", "rcc_enclosed")
    stair_rate  = {"rcc_open": 55000, "rcc_enclosed": 80000,
                   "fire_rated": 130000, "smoke_lobby": 200000}.get(stair_type, 80000)
    stair_cost  = num_stairs * stair_rate * floors

    walls_cost = masonry + plaster + openings + facade_cost + stair_cost

    # ── Flooring & Slab ──
    slab_concrete = sqft * floors * 200 * conc_fac * slab_fac
    steel_cost    = sqft * floors * 4.0 * 65 * steel_fac

    floor_type    = form.get("apt_flooring_type", "vitrified")
    floor_rate    = FLOORING_RATE.get(floor_type, 90)
    flooring_mat  = sqft * (1 - ca_pct) * floor_rate   # only saleable area

    bath_tile     = form.get("apt_bathroom_tile", "ceramic_standard")
    bath_tile_rate= BATH_TILE_RATE.get(bath_tile, 80)
    bath_wall_area= total_baths * 7 * (ceiling_ht * 0.65)
    bath_tile_cost= bath_wall_area * bath_tile_rate

    flooring_cost = slab_concrete + steel_cost + flooring_mat + bath_tile_cost

    # ── Roofing ──
    roofing_cost = (sqft / floors) * 190 * conc_fac * slab_fac   # top slab only

    # ── Plumbing (per unit scaled) ──
    pipe_mat    = "cpvc"
    pipe_rate   = PIPE_RATE.get(pipe_mat, 150)
    total_pipe  = (total_baths * 22) + (floors * 50) + total_units * 15
    pipe_cost   = total_pipe * pipe_rate

    san_grade   = form.get("apt_sanitary_grade", "standard")
    san_rate    = SANITARY_RATE.get(san_grade, 11500)
    san_cost    = san_rate * total_baths

    sump_cost   = 80000 + total_units * 1500  # communal sump
    plumbing_cost = pipe_cost + san_cost + sump_cost

    # ── Electrical ──
    num_sw      = int(form.get("apt_num_switchboards") or 0) or total_units * 8
    num_ac      = int(form.get("apt_num_ac_points") or 0)
    wiring      = form.get("apt_wiring_type", "fr_pvc")
    inv         = form.get("apt_inverter_wiring", "partial")
    earth       = form.get("apt_earthing_system", "plate")

    wire_rft    = sqft * 2.5
    wire_cost   = wire_rft * WIRING_RATE.get(wiring, 30)
    sw_cost     = num_sw * 1800
    ac_cost     = num_ac * 4500
    earth_cost  = EARTHING_RATE.get(earth, 6000) * floors
    inv_cost    = {"none": 0, "partial": 30000, "full": total_units * 8000}.get(inv, 30000)

    # Lifts
    num_lifts   = int(form.get("apt_lifts") or 0)
    lift_cap    = form.get("apt_lift_capacity", "8")
    lift_cost   = {"6": 1200000, "8": 1800000, "13": 2800000,
                   "service": 2200000}.get(str(lift_cap), 1800000) * num_lifts

    # DG
    dg = form.get("apt_dg_backup", "common_only")
    dg_cost = {"none": 0, "common_only": 350000, "partial": total_units*18000,
               "full": total_units*40000}.get(dg, 350000)

    electrical_cost = wire_cost + sw_cost + ac_cost + earth_cost + inv_cost + lift_cost + dg_cost

    # ── Finishing (paint + false ceiling per unit) ──
    int_paint     = form.get("apt_internal_paint", "emulsion")
    int_p_rate    = INTERNAL_PAINT_RATE.get(int_paint, 23)
    int_paint_cost= wall_info["int_net"] * (18 + int_p_rate)

    fc_per_unit   = form.get("apt_false_ceiling", "none")
    fc_area_per   = _false_ceiling_area(sqft / max(total_units, 1), fc_per_unit)
    fc_total      = fc_area_per * total_units * FALSE_CEILING_RATE

    finishing_cost = int_paint_cost + fc_total

    # ── Carpentry (per unit kitchen + wardrobes) ──
    kt_type       = form.get("apt_kitchen_type", "semi_modular")
    kp_length_avg = 8   # assumed per flat (no individual input for apt)
    modular_extra = KITCHEN_PLATFORM_RATE.get(kt_type, 0) * kp_length_avg * total_units
    carpentry_cost = sqft * 40 + modular_extra

    # ── Exterior / Amenities ──
    exterior_cost = 0

    # Parking
    park_slots  = int(form.get("apt_parking_slots") or 0)
    park_floor  = form.get("apt_parking_floor", "epoxy")
    park_rate   = {"pcc": 90, "epoxy": 180, "interlocking": 160,
                   "polished_concrete": 220, "anti_skid_ramp": 140}.get(park_floor, 180)
    slot_area   = park_slots * float(form.get("apt_slot_length") or 18) * float(form.get("apt_slot_width") or 8.5)
    exterior_cost += slot_area * park_rate

    # Pool (apt)
    apt_pool    = form.get("apt_pool", "none")
    if apt_pool != "none":
        pool_area_map = {"small": 600, "standard": 1200, "lap_pool": 1600}
        pa = pool_area_map.get(apt_pool, 600)
        pool_fin  = POOL_FINISH_RATE.get(form.get("apt_pool_finish", "vitrified_tile"), 200)
        exterior_cost += pa * (pool_fin + 1200)   # shell + finish

    # Clubhouse
    ch = form.get("apt_clubhouse", "none")
    ch_cost_map = {"none": 0, "basic": 1500000, "standard": 4000000, "full": 10000000}
    exterior_cost += ch_cost_map.get(ch, 0)

    # Safety systems
    fire_spec = form.get("apt_fire_spec", "wet_riser")
    fire_cost = {"wet_riser": 800 * sqft / floors, "sprinkler_full": 1400 * sqft / floors,
                 "both": 2000 * sqft / floors}.get(fire_spec, 800 * sqft / floors)
    exterior_cost += fire_cost

    # STP
    if form.get("apt_stp_type"):
        stp_cost_map = {"stp_only": 800000, "stp_rwh": 1200000, "stp_wtp_rwh": 2000000}
        exterior_cost += stp_cost_map.get(form.get("apt_stp_type", "stp_only"), 800000)

    # CCTV
    sec_level = form.get("apt_security_level", "")
    if sec_level:
        exterior_cost += {"basic": 120000, "standard": total_units*8000,
                          "smart": total_units*18000}.get(sec_level, 0)

    # Solar
    solar_kw = float(form.get("apt_solar_kw") or 0)
    exterior_cost += solar_kw * 55000

    # Landscape
    landscape = form.get("apt_landscape", "none")
    ls_sqft   = max(0, plot_area - sqft / floors)  # approx green area
    ls_rate   = {"none": 0, "basic": 60, "designed": 180, "terrace": 250}.get(landscape, 0)
    exterior_cost += ls_sqft * ls_rate

    # ── Miscellaneous ──
    misc_cost = sqft * floors * 40

    stage_breakdown = {
        "foundation":    round(foundation_cost, 0),
        "walls":         round(walls_cost, 0),
        "flooring":      round(flooring_cost, 0),
        "roofing":       round(roofing_cost, 0),
        "plumbing":      round(plumbing_cost, 0),
        "electrical":    round(electrical_cost, 0),
        "finishing":     round(finishing_cost, 0),
        "carpentry":     round(carpentry_cost, 0),
        "exterior":      round(exterior_cost, 0),
        "miscellaneous": round(misc_cost, 0),
    }
    return stage_breakdown


# ─────────────────────────────────────────────────────────────────
#  COST TIER SCALING  (low / medium / high)
# ─────────────────────────────────────────────────────────────────

TIER_FACTOR = {"low": 0.75, "medium": 1.00, "high": 1.40}

def _build_cost_tiers(base_breakdown: dict, scope: str) -> dict:
    """
    Given the base (medium) stage breakdown, produce low/medium/high variants.
    scope: "material_only" → no labour; "material_and_labour" → +22% labour line
    """
    all_costs = {}
    labour_pct = 0.22 if scope == "material_and_labour" else 0.0
    other_pct  = 0.025

    for tier, fac in TIER_FACTOR.items():
        stage_costs = {k: round(v * fac, 0) for k, v in base_breakdown.items()}
        mat_cost    = sum(stage_costs.values())
        lab_cost    = round(mat_cost * labour_pct, 0)
        oth_cost    = round(mat_cost * other_pct, 0)
        total       = mat_cost + lab_cost + oth_cost

        all_costs[tier] = {
            "material_cost":   round(mat_cost, 0),
            "labor_cost":      round(lab_cost, 0),
            "other_costs":     round(oth_cost, 0),
            "total_cost":      round(total, 0),
            "stage_breakdown": stage_costs,
        }
    return all_costs


# ─────────────────────────────────────────────────────────────────
#  MATERIAL QUANTITIES  (BOQ, maps to existing template keys)
# ─────────────────────────────────────────────────────────────────

def _build_quantities(sqft: float, floors: int, rooms: int, bathrooms: int,
                      ceiling_ht: float, form: dict, prefix: str = "") -> dict:
    """Returns the same structure as the old 'materials' dict."""
    p = prefix
    def f(key, default=None):
        return form.get(f"{p}{key}", form.get(key, default))

    slab_fac  = SLAB_THICKNESS_FACTOR.get(float(f("slab_thickness", 5)), 1.0)
    conc_fac  = CONCRETE_GRADE_FACTOR.get(f("concrete_grade", "M20"), 1.0)
    steel_fac = STEEL_GRADE_FACTOR.get(f("steel_grade", "Fe500"), 1.0)

    num_doors   = int(f("num_doors",   6))
    num_windows = int(f("num_windows", 8))

    foundation = {
        "cement_bags":       round(sqft * 0.175 * floors * conc_fac * slab_fac, 1),
        "sand_cuft":         round(sqft * 0.525 * floors * slab_fac, 1),
        "aggregate_cuft":    round(sqft * 0.70  * floors * slab_fac, 1),
        "steel_kg":          round(sqft * 3.5   * floors * steel_fac, 1),
        "concrete_blocks":   int(sqft  * 2.8 * slab_fac),
        "water_liters":      round(sqft * 18 * floors, 1),
        "waterproofing_kg":  round(sqft * 0.18, 1),
    }

    wm = WALL_MATERIAL_RATE.get(f("wall_material", "red_clay"), WALL_MATERIAL_RATE["red_clay"])
    wall_info = _wall_areas(sqft, floors, ceiling_ht, num_doors, num_windows)
    walls = {
        "bricks_or_blocks": int(wall_info["total_gross"] * wm["bags_per_sqft"] * 4.5),
        "cement_bags":      round(wall_info["total_gross"] * wm["bags_per_sqft"], 1),
        "sand_cuft":        round(wall_info["total_gross"] * wm["bags_per_sqft"] * 2.5, 1),
        "doors":            num_doors,
        "windows":          num_windows,
        "internal_plaster_sqft": round(wall_info["int_net"], 1),
        "external_plaster_sqft": round(wall_info["ext_net"], 1),
    }

    floor_type = f("flooring_type", "vitrified")
    flooring = {
        "cement_bags":    round(sqft * 0.15 * floors * conc_fac * slab_fac, 1),
        "sand_cuft":      round(sqft * 0.38 * floors * slab_fac, 1),
        "steel_kg":       round(sqft * 3.04 * floors * steel_fac, 1),
        "aggregate_cuft": round(sqft * 0.57 * floors * slab_fac, 1),
        "floor_tiles_sqft": round(sqft * floors * 0.70, 1),
        "bathroom_wall_tiles_sqft": round(bathrooms * 7 * ceiling_ht * 0.65, 1),
        "shuttering_sqft":round(sqft * floors * 0.48, 1),
    }

    roofing = {
        "steel_kg":         round(sqft * 4.4  * steel_fac, 1),
        "cement_bags":      round(sqft * 0.22 * conc_fac * slab_fac, 1),
        "sand_cuft":        round(sqft * 0.44 * slab_fac, 1),
        "aggregate_cuft":   round(sqft * 0.66 * slab_fac, 1),
        "waterproofing_sqft": round(sqft / floors, 1),
    }

    total_pipe = (bathrooms * 22) + (floors * 50) + 30
    plumbing = {
        "pvc_pipes_meters":  round(total_pipe * 0.40, 1),
        "cpvc_pipes_meters": round(total_pipe * 0.35, 1),
        "gi_pipes_meters":   round(total_pipe * 0.15, 1),
        "water_tank_liters": int(f("overhead_tank_capacity", 1000) or 1000),
        "taps":              int(f("num_taps", bathrooms * 4 + 4)),
        "washbasin":         bathrooms,
        "toilets":           bathrooms,
        "kitchen_sink":      1,
        "valves":            bathrooms * 3 + 3,
        "showers":           int(f("num_showers", bathrooms)),
    }

    electrical = {
        "wiring_meters":    round(sqft * floors * 2.5, 1),
        "switches":         rooms * 3 + bathrooms * 2,
        "sockets":          rooms * 4 + bathrooms * 2,
        "fans":             rooms + 1,
        "lights":           rooms * 2 + bathrooms + 3,
        "mcb_breakers":     6 + (floors * 2),
        "distribution_box": floors,
        "conduits_meters":  round(sqft * 1.5, 1),
        "ac_points":        int(f("num_ac_points", 0)),
    }

    kp_len   = float(f("kitchen_platform_length", 10) or 10)
    fc_area  = _false_ceiling_area(sqft, f("false_ceiling_yn", "no") or f("false_ceiling", "no"))
    finishing = {
        "putty_kg":        round(wall_info["int_net"] * 0.8, 1),
        "primer_liters":   round(wall_info["int_net"] * 0.06, 1),
        "interior_paint_liters": round(wall_info["int_net"] * 0.08, 1),
        "exterior_paint_liters": round(wall_info["ext_net"] * 0.07, 1),
        "false_ceiling_sqft": round(fc_area, 1),
        "kitchen_platform_sqft": round(kp_len * 2.5, 1),
    }

    carpentry = {
        "plywood_sheets":   round(rooms * 3.2, 1),
        "laminate_sqft":    round(rooms * 20, 1),
        "mdf_sheets":       round(rooms * 1.6, 1),
        "wardrobes":        max(1, rooms - 1),
        "hinges":           (rooms * 6) + (bathrooms * 3),
        "handles":          (rooms * 4) + (bathrooms * 2),
    }

    exterior = {
        "car_porch_sqft":    float(f("car_porch_sqft") or 200),
        "boundary_wall_rft": float(f("boundary_rft") or 0),
        "garden_sqft":       float(f("garden_sqft") or 0),
        "sump_capacity_liters": int(f("sump_capacity", 5000) or 5000),
    }

    miscellaneous = {
        "waterproofing_chem_kg": round(sqft * 0.12, 1),
        "binding_wire_kg":        round(sqft * 0.04, 1),
        "safety_equipment_sets":  max(1, floors),
        "nails_kg":               round(sqft * 0.02, 1),
    }

    return {
        "foundation":   foundation,
        "walls":        walls,
        "flooring":     flooring,
        "roofing":      roofing,
        "plumbing":     plumbing,
        "electrical":   electrical,
        "finishing":    finishing,
        "carpentry":    carpentry,
        "exterior":     exterior,
        "miscellaneous": miscellaneous,
    }


# ─────────────────────────────────────────────────────────────────
#  TIMELINE (unchanged logic, calibrated per stage)
# ─────────────────────────────────────────────────────────────────

def _build_timeline(sqft: float, floors: int, rooms: int) -> dict:
    tl = {
        "foundation":  round(sqft / 44,  0),
        "walls":       round(sqft / 36,  0),
        "flooring":    round(sqft / 57,  0),
        "roofing":     round(sqft / 67,  0),
        "plumbing":    round(sqft / 100, 0),
        "electrical":  round(sqft / 100, 0),
        "finishing":   round(sqft / 44,  0),
        "carpentry":   round(rooms * 7,  0),
        "exterior":    round(sqft / 167, 0),
    }
    tl["total_days"] = int(sum(tl.values()))
    return tl


# ─────────────────────────────────────────────────────────────────
#  AI REFINEMENT (calls Anthropic API for edge-case adjustments)
# ─────────────────────────────────────────────────────────────────

def _ai_refine_estimate(base_costs: dict, form: dict, sqft: float,
                        property_type: str) -> dict:
    """
    Calls Claude to review the computed base estimate for sanity and
    return any stage-level adjustment factors (0.8–1.3).
    Returns a dict of {stage: factor} or empty dict on failure.
    """
    import json, requests

    summary = {
        "sqft": sqft,
        "property_type": property_type,
        "location": form.get("location", "India"),
        "base_total_medium": base_costs.get("medium", {}).get("total_cost", 0),
        "stages": {k: v for k, v in base_costs.get("medium", {}).get("stage_breakdown", {}).items()},
        "key_inputs": {
            "concrete_grade": form.get("concrete_grade") or form.get("villa_concrete_grade") or form.get("apt_concrete_grade"),
            "steel_grade":    form.get("steel_grade") or form.get("villa_steel_grade") or form.get("apt_steel_grade"),
            "slab_thickness": form.get("slab_thickness") or form.get("villa_slab_thickness") or form.get("apt_slab_thickness"),
            "soil_condition": form.get("soil_condition") or form.get("villa_soil_condition") or form.get("apt_soil_condition"),
            "foundation_type":form.get("foundation_type") or form.get("villa_foundation_type") or form.get("apt_foundation_type"),
            "sanitary_grade": form.get("sanitary_grade") or form.get("villa_sanitary_grade") or form.get("apt_sanitary_grade"),
            "flooring":       form.get("flooring_type") or form.get("villa_flooring_grade") or form.get("apt_flooring_type"),
        }
    }

    prompt = f"""You are a senior construction cost estimator in India.
Review this construction estimate for a {property_type} of {sqft} sqft and respond ONLY with a JSON object (no preamble, no markdown).

Input data:
{json.dumps(summary, indent=2)}

Return exactly this JSON structure with adjustment factors between 0.75 and 1.35 for each stage.
A factor of 1.0 means the estimate is reasonable. Go higher if the spec warrants it, lower if over-estimated.
Also return a brief "rationale" string (max 40 words) and a "confidence" score 1-10.

{{
  "foundation":    1.0,
  "walls":         1.0,
  "flooring":      1.0,
  "roofing":       1.0,
  "plumbing":      1.0,
  "electrical":    1.0,
  "finishing":     1.0,
  "carpentry":     1.0,
  "exterior":      1.0,
  "miscellaneous": 1.0,
  "rationale": "...",
  "confidence": 8
}}"""

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"Content-Type": "application/json"},
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 512,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=12
        )
        if resp.status_code == 200:
            data = resp.json()
            text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
            # Strip any stray markdown fences
            text = text.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
            factors = json.loads(text)
            return factors
    except Exception as e:
        print(f"[AI refine] skipped: {e}")
    return {}


def _apply_ai_factors(costs: dict, factors: dict) -> dict:
    """Apply per-stage AI adjustment factors to all tiers."""
    if not factors:
        return costs
    stage_keys = ["foundation","walls","flooring","roofing","plumbing",
                  "electrical","finishing","carpentry","exterior","miscellaneous"]
    for tier in costs:
        for stage in stage_keys:
            fac = float(factors.get(stage, 1.0))
            fac = max(0.75, min(1.35, fac))  # clamp to safe range
            costs[tier]["stage_breakdown"][stage] = round(
                costs[tier]["stage_breakdown"][stage] * fac, 0)
        # Recompute totals
        mat = sum(costs[tier]["stage_breakdown"].values())
        lab = costs[tier]["labor_cost"]
        oth = costs[tier]["other_costs"]
        if lab > 0:
            lab = round(mat * 0.22, 0)
        oth = round(mat * 0.025, 0)
        costs[tier]["material_cost"] = round(mat, 0)
        costs[tier]["labor_cost"]    = lab
        costs[tier]["other_costs"]   = oth
        costs[tier]["total_cost"]    = round(mat + lab + oth, 0)
    return costs


# ─────────────────────────────────────────────────────────────────
#  PUBLIC ENTRY POINT  (replaces old calculate_materials_and_cost)
# ─────────────────────────────────────────────────────────────────

def calculate_materials_and_cost(square_feet, rooms, floors, bathrooms,
                                  budget_range, form: Optional[dict] = None):
    """
    Main function called from user_routes.py.
    Now accepts the full Flask request.form as `form` for detailed calculation.
    Falls back to the legacy 4-arg mode when form is None.
    """
    if form is None:
        form = {}

    sqft       = float(square_feet)
    floors     = max(1, int(floors))
    rooms      = max(1, int(rooms))
    bathrooms  = max(1, int(bathrooms))
    plot_area  = float(form.get("plot_area") or sqft * 1.3)
    prop_type  = form.get("property_type", "residential")
    scope      = form.get("estimate_scope", "material_only")
    ceiling_ht = float(form.get("ceiling_height") or form.get("villa_ceiling_height") or
                       form.get("apt_ceiling_height") or 10)

    # ── Pick the right sub-calculator ──
    if prop_type == "villa":
        base_bd = _calc_residential(form, sqft, plot_area, floors,
                                    bathrooms, rooms, ceiling_ht, prefix="villa_")
    elif prop_type == "apartment":
        base_bd = _calc_apartment(form, sqft, plot_area, floors)
    else:
        base_bd = _calc_residential(form, sqft, plot_area, floors,
                                    bathrooms, rooms, ceiling_ht, prefix="")

    # ── Build three-tier costs ──
    costs = _build_cost_tiers(base_bd, scope)

    # ── AI refinement (non-blocking) ──
    ai_factors = _ai_refine_estimate(costs, form, sqft, prop_type)
    costs      = _apply_ai_factors(costs, ai_factors)

    # ── Material quantities ──
    if prop_type == "villa":
        materials = _build_quantities(sqft, floors, rooms, bathrooms,
                                      ceiling_ht, form, prefix="villa_")
    elif prop_type == "apartment":
        # For apartment, derive representative unit counts
        total_units = int(form.get("apt_total_units") or 1)
        avg_baths   = max(1, (int(form.get("apt_1bhk_count") or 0)
                            + int(form.get("apt_2bhk_count") or 0)*2
                            + int(form.get("apt_3bhk_count") or 0)*3) // max(total_units, 1))
        materials = _build_quantities(sqft, floors, rooms or total_units*2,
                                      avg_baths or bathrooms, ceiling_ht, form, prefix="")
    else:
        materials = _build_quantities(sqft, floors, rooms, bathrooms,
                                      ceiling_ht, form, prefix="")

    # ── Timeline ──
    timeline = _build_timeline(sqft, floors, rooms)

    return {
        "materials":             materials,
        "costs":                 costs,
        "timeline":              timeline,
        "selected_budget":       budget_range,
        "total_materials_count": sum(len(s) for s in materials.values()),
        "ai_rationale":          ai_factors.get("rationale", ""),
        "ai_confidence":         ai_factors.get("confidence", ""),
        "estimate_scope":        scope,
        "property_type":         prop_type,
    }