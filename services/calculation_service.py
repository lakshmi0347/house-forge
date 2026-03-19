"""
House-Forge Construction Estimation Service
============================================
Rate tables: 2025-26 Indian market prices (March 2026).
Prices are hardcoded reference rates — updated manually each quarter.
AI refinement applies per-stage adjustment factors on top of these base rates.

FIXES in this version:
  1. Steel base price unified to ₹63/kg everywhere (was ₹65 in code vs ₹63 in docstring).
  2. AI failure now sets a visible rationale string instead of silent fallback.
  3. STEEL_BASE_PRICE constant introduced — single place to update.
  4. Apartment steel cost also uses STEEL_BASE_PRICE.
  5. Minor: _ai_refine_estimate returns confidence=0 on failure so UI can detect it.
"""

import math
from typing import Optional

# ─────────────────────────────────────────────────────────────────
#  SINGLE-SOURCE PRICE CONSTANTS  (update here each quarter)
# ─────────────────────────────────────────────────────────────────

STEEL_BASE_PRICE = 63        # ₹/kg  Fe500 TMT  (March 2026)
SLAB_CONCRETE_BASE = 72      # ₹/sqft/floor  RMC + labour + shuttering
SLAB_CONCRETE_APT  = 68      # ₹/sqft/floor  apartment grade
MISC_PER_SQFT_FLOOR = 45     # ₹/sqft/floor  residential miscellaneous
MISC_APT_PER_SQFT   = 48     # ₹/sqft/floor  apartment miscellaneous
CARPENTRY_BASE_RES  = 68     # ₹/sqft  residential carpentry
CARPENTRY_BASE_VILLA= 102    # ₹/sqft  villa carpentry (1.5× residential)
CARPENTRY_BASE_APT  = 50     # ₹/sqft  apartment carpentry

# ─────────────────────────────────────────────────────────────────
#  RATE TABLES  ·  Updated March 2026
# ─────────────────────────────────────────────────────────────────

CONCRETE_GRADE_FACTOR = {"M20": 1.00, "M25": 1.08, "M30": 1.16, "M35": 1.25, "M40": 1.35}
STEEL_GRADE_FACTOR    = {"Fe500": 1.00, "Fe550": 1.06, "Fe500D": 1.04}
SLAB_THICKNESS_FACTOR = {4.5: 0.90, 5: 1.00, 5.5: 1.10, 6: 1.20}

# ── Foundation (₹/sqft of BUA) ─────────────────────────────────
FOUNDATION_RATE = {
    "isolated": {"rate_per_sqft_bua": 260},
    "strip":    {"rate_per_sqft_bua": 310},
    "raft":     {"rate_per_sqft_bua": 410},
    "pile":     {"rate_per_sqft_bua": 640},
    "combined": {"rate_per_sqft_bua": 360},
}

# ── Extra cost for difficult soil (₹/sqft) ──────────────────────
SOIL_EXTRA_RATE = {
    "hard_rock": 0,
    "firm_soil": 0,
    "soft_soil": 52,
    "marshy":    155,
    "filled":    100,
}

# ── Wall masonry (₹/sqft wall area, supply+fix incl mortar) ──────
WALL_MATERIAL_RATE = {
    "red_clay":        {"mat_rate": 8.5,  "bags_per_sqft": 0.30},
    "aac_blocks":      {"mat_rate": 11.5, "bags_per_sqft": 0.22},
    "fly_ash":         {"mat_rate": 9.5,  "bags_per_sqft": 0.26},
    "hollow_concrete": {"mat_rate": 9.0,  "bags_per_sqft": 0.24},
}

# ── Plaster (₹/sqft net wall area, supply+fix) ──────────────────
PLASTER_RATE = {
    "12mm_cm":       22,
    "20mm_cm":       27,
    "gypsum":        38,
    "skim_coat":     18,
    "12mm_cm_15":    24,
    "20mm_cm_14":    30,
    "textured_coat": 48,
    "none":           0,
    "drywall":       60,
}

# ── Doors (₹/door, supply+fix frame+shutter) ────────────────────
DOOR_RATE = {
    "flush_hollow":   12000,
    "flush_solid":    28000,
    "panel_teak":     60000,
    "upvc_door":      32000,
    "aluminium_door": 38000,
    "designer_wood":  120000,
}

# ── Windows (₹/window, supply+fix) ──────────────────────────────
WINDOW_RATE = {
    "ms_grill":          7000,
    "aluminium_sliding": 17000,
    "upvc_casement":     28000,
    "upvc_sliding":      22000,
    "wooden_frame":      40000,
}

# ── Flooring (₹/sqft, supply+fix incl bedding) ──────────────────
FLOORING_RATE = {
    "vitrified":       110,
    "marble":          300,
    "granite":         240,
    "hardwood":        420,
    "ceramic":          75,
    "italian_marble":  700,
    "premium_granite": 360,
    "natural_stone":   450,
}

# ── Bathroom wall tiles (₹/sqft, supply+fix to dado height) ──────
BATH_TILE_RATE = {
    "ceramic_economy":    55,
    "ceramic_standard":  100,
    "vitrified_wall":    140,
    "designer_tiles":    310,
    "natural_stone_bath":450,
}

# ── Paint (₹/sqft, primer + 2 coats, supply+labour) ────────────
INTERNAL_PAINT_RATE = {
    "emulsion": 28,
    "luxury":   48,
    "texture":  90,
}
EXTERNAL_PAINT_RATE = {
    "weathershield": 35,
    "elastomeric":   58,
    "texture_ext":  100,
}

# ── Common area finishes (apartments) ────────────────────────────
COMMON_FLOORING_RATE = {
    "vitrified": 110,
    "marble":    300,
    "granite":   240,
    "ceramic":    75,
}
COMMON_PAINT_RATE = {
    "emulsion": 28,
    "luxury":   48,
    "texture":  90,
}
COMMON_CEILING_RATE = {
    "painted":          0,
    "gypsum_plain":    82,
    "gypsum_designer": 155,
    "metal_grid":      120,
}
LOBBY_WALL_RATE = {
    "paint_only":      0,
    "ceramic_dado":   75,
    "vitrified_full": 140,
    "stone_cladding": 360,
}

# ── False ceiling — gypsum board installed (₹/sqft) ──────────────
FALSE_CEILING_RATE = 105

# ── Kitchen ──────────────────────────────────────────────────────
KITCHEN_PLATFORM_RATE = {
    "semi_modular": 0,
    "modular":      4200,   # ₹/rft
}
KITCHEN_STONE_RATE = {
    "granite_standard": 280,
    "granite_premium":  560,
    "quartz":           800,
    "marble_kitchen":   460,
    "ceramic_tiles":    110,
}

# ── Plumbing — pipes (₹/rft installed) ───────────────────────────
PIPE_RATE = {
    "cpvc": 180,
    "upvc": 100,
    "ppr":  170,
    "gi":   220,
}

# ── Sanitary ware sets (₹/bathroom, supply only) ─────────────────
SANITARY_RATE = {
    "standard":  15000,
    "mid":       34000,
    "premium":   78000,
    "luxury":   130000,
}

# ── Electrical wiring (₹/rft installed) ──────────────────────────
WIRING_RATE = {
    "fr_pvc":   38,
    "lszh":     60,
    "armoured": 80,
}

# ── Earthing (₹/system) ──────────────────────────────────────────
EARTHING_RATE = {
    "plate":     8000,
    "pipe":      6000,
    "chemical": 16000,
}

# ── Waterproofing (₹/sqft treated area) ──────────────────────────
WATERPROOFING_RATE = {
    "brick_bat_coba": 52,
    "chemical_coat":  36,
    "membrane":       82,
    "crystalline":   130,
    "none":            0,
}

# ── Anti-termite (₹/sqft of plot area) ───────────────────────────
ANTI_TERMITE_RATE = {
    "pre_construction":  14.0,
    "post_construction": 10.0,
    "none":               0,
}

# ── Swimming pool finishes (₹/sqft pool surface) ─────────────────
POOL_FINISH_RATE = {
    "ceramic_tile":       140,
    "vitrified_tile":     250,
    "glass_mosaic":       580,
    "fibreglass":         680,
    "exposed_aggregate":  340,
}

# ── Pool deck (₹/sqft deck area) ─────────────────────────────────
POOL_DECK_RATE = {
    "anti_skid_granite": 220,
    "natural_stone":     460,
    "composite_deck":    310,
    "ceramic_anti_skid": 150,
}

# ── Landscaping (₹/sqft) ─────────────────────────────────────────
LANDSCAPING_RATE = {
    "basic":    75,
    "standard": 145,
    "premium":  280,
    "luxury":   560,
}

# ── External cladding on wall area (₹/sqft) ──────────────────────
CLADDING_RATE = {
    "plaster":       0,
    "stone":       520,
    "glass_facade":2000,
    "composite":   400,
}

# ── Apartment facade (₹/sqft external wall area) ─────────────────
FACADE_RATE = {
    "plaster_paint":  120,
    "texture_paint":  175,
    "acp_cladding":   400,
    "stone_cladding": 520,
    "glass_curtain": 1500,
}

# ── Porch / driveway flooring (₹/sqft) ───────────────────────────
PORCH_FLOOR_RATE = {
    "granite":          250,
    "cobblestone":      200,
    "stamped_concrete": 225,
    "natural_stone":    460,
}

# ── External site development (₹/sqft) ───────────────────────────
EXTERNAL_DEV_RATE = {
    "basic":    125,
    "standard": 200,
    "premium":  380,
}


# ─────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────

def _wall_areas(sqft, floors, ceiling_ht, num_doors, num_windows, outer_wall_ratio=0.45):
    side      = math.sqrt(sqft / max(floors, 1))
    perimeter = 4 * side
    ext_gross = perimeter * ceiling_ht * floors
    int_gross = ext_gross * (1 - outer_wall_ratio) / outer_wall_ratio
    void_total= num_doors * 21 + num_windows * 16
    ext_net   = max(0, ext_gross - void_total * outer_wall_ratio)
    int_net   = max(0, int_gross - void_total * (1 - outer_wall_ratio))
    return {
        "ext_gross": ext_gross, "int_gross": int_gross,
        "ext_net":   ext_net,   "int_net":   int_net,
        "total_gross": ext_gross + int_gross,
    }


def _false_ceiling_area(sqft, coverage):
    c = str(coverage or "").lower().strip()
    if c in ("no", "none", ""):
        return 0.0
    if c == "partial":
        return sqft * 0.35
    if c == "full":
        return sqft * 1.0
    return 0.0


def _safe_int(val, default=0):
    try:
        return int(val or default)
    except (ValueError, TypeError):
        return default


def _safe_float(val, default=0.0):
    try:
        return float(val or default)
    except (ValueError, TypeError):
        return default


# ─────────────────────────────────────────────────────────────────
#  RESIDENTIAL / VILLA CORE CALCULATOR
# ─────────────────────────────────────────────────────────────────

def _calc_residential(form, sqft, plot_area, floors, bathrooms, rooms, ceiling_ht, prefix=""):
    p = prefix

    def f(key, default=None):
        return form.get(f"{p}{key}", form.get(key, default))

    conc_fac   = CONCRETE_GRADE_FACTOR.get(f("concrete_grade", "M20"), 1.0)
    steel_fac  = STEEL_GRADE_FACTOR.get(f("steel_grade", "Fe500"), 1.0)
    slab_fac   = SLAB_THICKNESS_FACTOR.get(_safe_float(f("slab_thickness", 5), 5.0), 1.0)
    struct_prem= 1.05 if form.get("structure_type", "rcc") == "rcc" else 1.0

    # 1. FOUNDATION
    fd_type  = f("foundation_type", "isolated")
    fd_depth = _safe_float(f("foundation_depth", 6), 6.0)
    soil_t   = f("soil_condition", "firm_soil")
    fd_rate  = (FOUNDATION_RATE.get(fd_type, FOUNDATION_RATE["isolated"])["rate_per_sqft_bua"]
                * (fd_depth / 6) * conc_fac * slab_fac * struct_prem)
    anti_t   = ANTI_TERMITE_RATE.get(f("anti_termite", "pre_construction"), 14.0)
    wproof   = WATERPROOFING_RATE.get(f("roof_waterproofing", "brick_bat_coba"), 52)
    foundation_cost = (fd_rate * sqft
                       + SOIL_EXTRA_RATE.get(soil_t, 0) * sqft
                       + anti_t * plot_area
                       + wproof * (sqft / max(floors, 1)))

    # 2. WALLS
    num_doors   = _safe_int(f("num_doors",   6), 6)
    num_windows = _safe_int(f("num_windows", 8), 8)
    wall_mat    = f("wall_material", "red_clay")
    wm          = WALL_MATERIAL_RATE.get(wall_mat, WALL_MATERIAL_RATE["red_clay"])
    wall_info   = _wall_areas(sqft, floors, ceiling_ht, num_doors, num_windows)
    outer_t     = _safe_float(f("wall_thickness", 9), 9.0) / 9
    inner_t     = _safe_float(f("inner_wall_thickness", 4.5), 4.5) / 9
    masonry     = (wall_info["ext_net"] * wm["mat_rate"] * outer_t
                   + wall_info["int_net"] * wm["mat_rate"] * inner_t)
    int_plas    = PLASTER_RATE.get(f("plaster_type", "12mm_cm"), 22)
    ext_plas    = PLASTER_RATE.get(f("external_plaster_type", "12mm_cm_15"), 24)
    plaster     = wall_info["int_net"] * int_plas + wall_info["ext_net"] * ext_plas
    door_mat    = f("door_material",   "flush_hollow")
    win_mat     = f("window_material", "aluminium_sliding")
    openings    = (DOOR_RATE.get(door_mat, 12000) * num_doors
                   + WINDOW_RATE.get(win_mat, 17000) * num_windows)
    walls_cost  = masonry + plaster + openings

    # 3. FLOORING & SLAB
    if prefix == "villa_":
        floor_type = f("flooring_grade", "italian_marble")
    else:
        floor_type = f("flooring_type", "vitrified")
    floor_rate = FLOORING_RATE.get(floor_type, 110)

    # FIX: use STEEL_BASE_PRICE constant (was magic number 65)
    slab_concrete = sqft * floors * SLAB_CONCRETE_BASE * conc_fac * slab_fac
    steel_cost    = sqft * 3.5 * STEEL_BASE_PRICE * steel_fac

    bath_tile      = f("bathroom_wall_tile", "ceramic_standard")
    bath_tile_rate = BATH_TILE_RATE.get(bath_tile, 100)
    bath_tile_cost = bathrooms * 7 * (ceiling_ht * 0.65) * bath_tile_rate

    cov_map      = {"full": 1.0, "ground_only": 1.0 / max(floors, 1), "partial_50": 0.5}
    cov_fac      = cov_map.get(f("flooring_coverage", "full"), 1.0)
    luxury_area  = sqft * cov_fac
    standard_area= sqft * (1.0 - cov_fac)
    flooring_cost= (luxury_area * floor_rate
                    + standard_area * FLOORING_RATE["vitrified"]
                    + slab_concrete + steel_cost + bath_tile_cost)

    # 4. ROOFING + STAIRCASE
    roof_type    = f("roof_type", "flat_rcc")
    roof_mult    = 1.15 if roof_type == "sloped_tiled" else 1.0
    roofing_cost = sqft * 200 * conc_fac * slab_fac * roof_mult

    if prefix == "villa_":
        stair_val = form.get("villa_staircase", "standard")
    else:
        stair_val = form.get("staircase_type", "rcc")

    stair_map = {
        "rcc": 75000, "standard": 75000, "spiral": 220000,
        "grand_marble": 560000, "steel_glass": 310000, "wooden": 250000, "none": 0,
    }
    roofing_cost += stair_map.get(stair_val, 75000) * max(1, floors - 1)

    # 5. PLUMBING
    pipe_rate  = PIPE_RATE.get(f("pipe_material", "cpvc"), 180)
    total_pipe = (bathrooms * 22) + (floors * 50) + 30
    num_taps   = _safe_int(f("num_taps", bathrooms * 4 + 4), bathrooms * 4 + 4)
    num_showers= _safe_int(f("num_showers", bathrooms), bathrooms)
    num_geysers= _safe_int(f("num_geysers", bathrooms), bathrooms)
    san_rate   = SANITARY_RATE.get(f("sanitary_grade", "standard"), 15000)
    sump_cap   = _safe_int(f("sump_capacity", 5000), 5000)
    sump_cost  = sump_cap * 1.0 + 42000
    ot_cap     = _safe_int(f("overhead_tank_capacity", 1000), 1000)
    ot_cost    = ot_cap * 0.6 + 5500
    plumbing_cost = (total_pipe * pipe_rate
                     + san_rate * bathrooms
                     + num_showers * 8500
                     + num_geysers * 4200
                     + num_taps * 1500
                     + sump_cost + ot_cost
                     + sqft * 18)

    # 6. ELECTRICAL
    num_sw  = _safe_int(f("num_switchboards", rooms * 2 + bathrooms + 3),
                        rooms * 2 + bathrooms + 3)
    num_ac  = _safe_int(f("num_ac_points", 0), 0)
    wiring  = f("wiring_type",     "fr_pvc")
    inv     = f("inverter_wiring", "none")
    earth   = f("earthing_system", "plate")
    electrical_cost = (sqft * floors * 2.5 * WIRING_RATE.get(wiring, 38)
                       + num_sw * 2200
                       + num_ac * 5500
                       + EARTHING_RATE.get(earth, 8000)
                       + {"none": 0, "partial": 18000, "full": 55000}.get(inv, 0))

    # 7. FINISHING
    int_paint  = f("internal_paint_quality", None) or f("internal_paint", "emulsion")
    ext_paint  = f("external_paint_quality", None) or f("external_paint", "weathershield")
    int_p_rate = INTERNAL_PAINT_RATE.get(int_paint, 28)
    ext_p_rate = EXTERNAL_PAINT_RATE.get(ext_paint, 35)
    int_paint_cost = wall_info["int_net"] * (22 + int_p_rate)
    ext_paint_cost = wall_info["ext_net"] * ext_p_rate

    if prefix == "villa_":
        fc_key = form.get("villa_false_ceiling", "no")
    else:
        fc_key = form.get("false_ceiling_yn", "no")
    fc_cost = _false_ceiling_area(sqft, fc_key) * FALSE_CEILING_RATE
    finishing_cost = int_paint_cost + ext_paint_cost + fc_cost

    # 8. CARPENTRY & KITCHEN
    kt_type   = f("kitchen_type", "semi_modular")
    kp_length = _safe_float(f("kitchen_platform_length", 10), 10.0)
    kp_stone  = f("kitchen_platform_stone", "granite_standard")
    kp_cost   = (kp_length * 2.5 * KITCHEN_STONE_RATE.get(kp_stone, 280)
                 + KITCHEN_PLATFORM_RATE.get(kt_type, 0) * kp_length)
    base_carp = sqft * (CARPENTRY_BASE_VILLA if prefix == "villa_" else CARPENTRY_BASE_RES)
    carpentry_cost = base_carp + kp_cost

    # 9. EXTERIOR
    exterior_cost = 0.0

    if prefix == "villa_":
        porch_sz = form.get("villa_car_porch_size")
    else:
        porch_sz = form.get("car_porch_size", "single")

    if porch_sz:
        porch_sqft_map = {"single": 200, "double": 400, "triple": 600}
        if prefix == "villa_":
            porch_sqft       = _safe_float(form.get("villa_car_porch_sqft"),
                                           porch_sqft_map.get(porch_sz, 200))
            porch_style      = form.get("villa_car_porch_style", "rcc_slab")
            porch_floor      = form.get("villa_porch_flooring", "granite")
            porch_floor_rate = PORCH_FLOOR_RATE.get(porch_floor, 250)
        else:
            porch_sqft       = _safe_float(form.get("car_porch_sqft"),
                                           porch_sqft_map.get(porch_sz, 200))
            porch_style      = "rcc_slab"
            porch_floor_rate = 0
        porch_style_rate = {
            "rcc_slab":        1050,
            "designer_canopy": 1700,
            "pergola_style":   1350,
            "arched":          1500,
        }.get(porch_style, 1050)
        exterior_cost += porch_sqft * (porch_style_rate + porch_floor_rate)

    if prefix == "villa_":
        garden_sqft = _safe_float(form.get("villa_garden_sqft"), 0)
        ls_grade    = form.get("villa_landscaping_grade", "standard")
        ls_rate     = LANDSCAPING_RATE.get(ls_grade, 145)
        vd_sqft = _safe_float(form.get("villa_driveway_sqft"), 0)
        vd_rate = {
            "interlocking_pavers": 200,
            "natural_stone_path":  460,
            "stamped_concrete":    260,
            "granite_cobble":      500,
        }.get(form.get("villa_driveway_finish", "interlocking_pavers"), 200)
        exterior_cost += vd_sqft * vd_rate
    else:
        garden_sqft = _safe_float(form.get("garden_sqft"), 0)
        ls_rate     = 75
    exterior_cost += garden_sqft * ls_rate

    if prefix == "villa_":
        bw_rft    = _safe_float(form.get("villa_boundary_rft"), 0)
        bw_height = _safe_float(form.get("villa_boundary_height", 8), 8.0)
        bw_finish = form.get("villa_boundary_finish", "stone_cladding")
        gate_cost = {
            "ms_fabricated":    55000,
            "sliding_auto":    140000,
            "swing_ornamental":110000,
            "ss_glass":        220000,
        }.get(form.get("villa_gate_type", "ms_fabricated"), 55000) if bw_rft else 0
    else:
        bw_rft    = _safe_float(form.get("boundary_rft"), 0)
        bw_height = 6.0
        bw_finish = form.get("boundary_finish", "plaster")
        gate_cost = 0

    bw_finish_rate = {
        "plaster":            220,
        "exposed":            150,
        "cladding":           390,
        "stone_cladding":     460,
        "composite_cladding": 355,
    }.get(bw_finish, 220)
    exterior_cost += bw_rft * bw_height * bw_finish_rate + gate_cost

    if prefix == "villa_":
        cladding = form.get("villa_cladding", "plaster")
        exterior_cost += wall_info["ext_net"] * CLADDING_RATE.get(cladding, 0)

        pl = _safe_float(form.get("pool_length"), 0)
        pw = _safe_float(form.get("pool_width"),  0)
        pd = _safe_float(form.get("pool_depth", 5), 5.0)
        if pl and pw:
            pool_plan_area = pl * pw
            pool_surface   = 2 * (pl * pd + pw * pd) + pl * pw
            pool_fin_rate  = POOL_FINISH_RATE.get(form.get("pool_finish", "vitrified_tile"), 250)
            pool_deck_rate = POOL_DECK_RATE.get(form.get("pool_deck", "anti_skid_granite"), 220)
            deck_area      = pool_plan_area * 1.5
            pool_structure = pool_plan_area * 7500
            exterior_cost += pool_structure + pool_surface * pool_fin_rate + deck_area * pool_deck_rate

    # 10. MISCELLANEOUS
    misc_cost = sqft * floors * MISC_PER_SQFT_FLOOR

    return {
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


# ─────────────────────────────────────────────────────────────────
#  APARTMENT CALCULATOR
# ─────────────────────────────────────────────────────────────────

def _calc_apartment(form, sqft, plot_area, floors):
    bhk1 = _safe_int(form.get("apt_1bhk_count"), 0)
    bhk2 = _safe_int(form.get("apt_2bhk_count"), 0)
    bhk3 = _safe_int(form.get("apt_3bhk_count"), 0)
    total_units = _safe_int(form.get("apt_total_units"), max(bhk1 + bhk2 + bhk3, 1))
    total_units = max(total_units, 1)
    total_baths = bhk1 * 1 + bhk2 * 2 + bhk3 * 3 or total_units * 2
    ceiling_ht  = _safe_float(form.get("apt_ceiling_height"), 10.0)
    ca_pct      = _safe_float(form.get("apt_common_area_pct"), 20.0) / 100

    conc_fac = CONCRETE_GRADE_FACTOR.get(form.get("apt_concrete_grade", "M30"), 1.16)
    steel_fac= STEEL_GRADE_FACTOR.get(form.get("apt_steel_grade", "Fe500D"), 1.04)
    slab_fac = SLAB_THICKNESS_FACTOR.get(_safe_float(form.get("apt_slab_thickness"), 5.0), 1.0)

    # Foundation
    fd_type  = form.get("apt_foundation_type", "raft")
    fd_depth = _safe_float(form.get("apt_foundation_depth"), 8.0)
    soil     = form.get("apt_soil_condition", "firm_soil")
    fd_cost  = (FOUNDATION_RATE.get(fd_type, FOUNDATION_RATE["raft"])["rate_per_sqft_bua"]
                * (fd_depth / 8) * conc_fac * slab_fac * sqft)
    anti_t   = ANTI_TERMITE_RATE.get(form.get("apt_anti_termite", "pre_construction"), 14.0) * plot_area
    wproof   = WATERPROOFING_RATE.get(form.get("apt_roof_waterproofing", "membrane"), 82) * (sqft / max(floors, 1))
    foundation_cost = fd_cost + SOIL_EXTRA_RATE.get(soil, 0) * sqft + anti_t + wproof

    park_type = form.get("apt_parking_type", "open")
    if park_type.startswith("basement"):
        b_depth  = _safe_float(form.get("apt_basement_depth"), 14.0)
        b_levels = 2 if park_type == "basement_2" else 1
        bw_rate  = WATERPROOFING_RATE.get(form.get("apt_basement_waterproofing", "membrane"), 82)
        foundation_cost += (sqft * b_depth * 0.15 * conc_fac * b_levels
                            + sqft * bw_rate * 0.4 * b_levels)

    # Walls
    wall_mat   = form.get("apt_wall_material", "aac_blocks")
    wm         = WALL_MATERIAL_RATE.get(wall_mat, WALL_MATERIAL_RATE["aac_blocks"])
    num_doors  = (bhk1 * 3 + bhk2 * 5 + bhk3 * 7) or total_units * 4
    num_windows= (bhk1 * 4 + bhk2 * 6 + bhk3 * 8) or total_units * 6
    wall_info  = _wall_areas(sqft, floors, ceiling_ht, num_doors, num_windows)
    outer_t    = _safe_float(form.get("apt_wall_thickness"), 9.0) / 9
    part_rate  = {"aac_blocks": 1.0, "fly_ash_partition": 0.9, "drywall": 1.3}.get(
                  form.get("apt_partition_material", "aac_blocks"), 1.0)
    masonry    = (wall_info["ext_net"] * wm["mat_rate"] * outer_t
                  + wall_info["int_net"] * wm["mat_rate"] * 0.5 * part_rate)
    int_plas   = PLASTER_RATE.get(form.get("apt_internal_plaster", "gypsum"), 38)
    ext_plas   = PLASTER_RATE.get(form.get("apt_external_plaster", "12mm_cm_15"), 24)
    plaster    = wall_info["int_net"] * int_plas + wall_info["ext_net"] * ext_plas
    door_mat   = form.get("apt_door_material",  "flush_solid")
    win_mat    = form.get("apt_window_material", "aluminium_sliding")
    openings   = (DOOR_RATE.get(door_mat, 28000) * num_doors
                  + WINDOW_RATE.get(win_mat, 17000) * num_windows)
    facade_t   = form.get("apt_facade_type", "plaster_paint")
    ext_paint  = EXTERNAL_PAINT_RATE.get(form.get("apt_external_paint", "weathershield"), 35)
    facade_cost= wall_info["ext_net"] * (FACADE_RATE.get(facade_t, 120) + ext_paint)
    num_stairs = _safe_int(form.get("apt_staircases"), 2)
    stair_t    = form.get("apt_staircase_type", "rcc_enclosed")
    stair_rate = {
        "rcc_open":     68000,
        "rcc_enclosed": 100000,
        "fire_rated":   160000,
        "smoke_lobby":  250000,
    }.get(stair_t, 100000)
    walls_cost = masonry + plaster + openings + facade_cost + num_stairs * stair_rate * floors

    # Flooring & Slab
    # FIX: use STEEL_BASE_PRICE constant
    slab_concrete  = sqft * floors * SLAB_CONCRETE_APT * conc_fac * slab_fac
    steel_cost     = sqft * 4.0 * STEEL_BASE_PRICE * steel_fac
    floor_type     = form.get("apt_flooring_type", "vitrified")
    flooring_mat   = sqft * (1 - ca_pct) * FLOORING_RATE.get(floor_type, 110)
    bath_tile      = form.get("apt_bathroom_tile", "ceramic_standard")
    bath_tile_cost = total_baths * 7 * (ceiling_ht * 0.65) * BATH_TILE_RATE.get(bath_tile, 100)
    flooring_cost  = slab_concrete + steel_cost + flooring_mat + bath_tile_cost

    # Roofing
    roofing_cost = (sqft / max(floors, 1)) * 200 * conc_fac * slab_fac

    # Plumbing
    pipe_cost    = ((total_baths * 22 + floors * 50 + total_units * 15) * PIPE_RATE["cpvc"])
    san_cost     = SANITARY_RATE.get(form.get("apt_sanitary_grade", "standard"), 15000) * total_baths
    ws_type  = form.get("apt_water_storage", "sump_overhead")
    ws_cost  = {"sump_overhead": 100000, "overhead": 38000,
                "borewell": 220000}.get(ws_type, 100000) + total_units * 1800
    plumbing_cost = pipe_cost + san_cost + ws_cost

    # Electrical
    num_sw     = total_units * 8 + floors * 2
    wire_cost  = sqft * 2.5 * WIRING_RATE["fr_pvc"]
    sw_cost    = num_sw * 2200
    earth_cost = EARTHING_RATE["plate"] * floors
    inv_cost   = total_units * 10000
    num_lifts  = _safe_int(form.get("apt_lifts"), 0)
    lift_cap   = form.get("apt_lift_capacity", "8")
    lift_cost  = {
        "6":       1500000,
        "8":       2200000,
        "13":      3500000,
        "service": 2800000,
    }.get(str(lift_cap), 2200000) * num_lifts
    dg_backup  = form.get("apt_dg_backup", "common_only")
    dg_cost    = {
        "none":        0,
        "common_only": 450000,
        "partial":     total_units * 22000,
        "full":        total_units * 50000,
    }.get(dg_backup, 450000)
    electrical_cost = wire_cost + sw_cost + earth_cost + inv_cost + lift_cost + dg_cost

    # Finishing
    int_paint    = form.get("apt_internal_paint", "emulsion")
    int_p_cost   = wall_info["int_net"] * (22 + INTERNAL_PAINT_RATE.get(int_paint, 28))

    fc_per        = form.get("apt_false_ceiling", "none")
    sqft_per_unit = (sqft * (1 - ca_pct)) / total_units
    fc_area       = _false_ceiling_area(sqft_per_unit, fc_per) * total_units
    fc_cost       = fc_area * FALSE_CEILING_RATE

    common_area_sqft  = sqft * ca_pct
    common_fl_rate    = COMMON_FLOORING_RATE.get(form.get("apt_common_flooring", "vitrified"), 110)
    common_fl_cost    = common_area_sqft * common_fl_rate
    common_paint_rate = COMMON_PAINT_RATE.get(form.get("apt_common_paint", "emulsion"), 28)
    common_wall_area  = (common_area_sqft / max(floors, 1)) * ceiling_ht * 0.6 * floors
    common_paint_cost = common_wall_area * (22 + common_paint_rate)
    common_ceil_rate  = COMMON_CEILING_RATE.get(form.get("apt_common_ceiling", "painted"), 0)
    common_ceil_cost  = common_area_sqft * common_ceil_rate
    lobby_wall_rate   = LOBBY_WALL_RATE.get(form.get("apt_lobby_wall_finish", "paint_only"), 0)
    lobby_area        = math.sqrt(common_area_sqft / max(floors, 1)) * 4 * ceiling_ht
    lobby_wall_cost   = lobby_area * lobby_wall_rate

    finishing_cost = (int_p_cost + fc_cost + common_fl_cost
                      + common_paint_cost + common_ceil_cost + lobby_wall_cost)

    # Carpentry
    kt_type        = form.get("apt_kitchen_type", "semi_modular")
    mod_extra      = KITCHEN_PLATFORM_RATE.get(kt_type, 0) * 8 * total_units
    carpentry_cost = sqft * CARPENTRY_BASE_APT + mod_extra

    # Exterior / Amenities
    exterior_cost = 0.0

    park_slots  = _safe_int(form.get("apt_parking_slots"), 0)
    park_rate   = {"pcc": 110, "epoxy": 220, "interlocking": 200,
                   "polished_concrete": 270, "anti_skid_ramp": 170}.get(
                   form.get("apt_parking_floor", "epoxy"), 220)
    slot_area   = (park_slots
                   * _safe_float(form.get("apt_slot_length"), 18.0)
                   * _safe_float(form.get("apt_slot_width"),  8.5))
    exterior_cost += slot_area * park_rate

    apt_pool = form.get("apt_pool", "none")
    if apt_pool != "none":
        pool_area = {"small": 600, "standard": 1200, "lap_pool": 1600}.get(apt_pool, 600)
        pool_fin  = POOL_FINISH_RATE.get(form.get("apt_pool_finish", "vitrified_tile"), 250)
        exterior_cost += pool_area * (pool_fin + 1500)

    exterior_cost += {
        "none": 0, "basic": 1800000, "standard": 5000000, "full": 12500000,
    }.get(form.get("apt_clubhouse", "none"), 0)

    ext_dev_sqft  = _safe_float(form.get("apt_external_dev_sqft"), 0)
    ext_dev_rate  = EXTERNAL_DEV_RATE.get(form.get("apt_external_dev_grade", "standard"), 200)
    exterior_cost += ext_dev_sqft * ext_dev_rate

    fire_spec = form.get("apt_fire_spec", "wet_riser")
    exterior_cost += {"wet_riser": 1000, "sprinkler_full": 1700, "both": 2500}.get(
                      fire_spec, 1000) * sqft / max(floors, 1)

    stp_type = form.get("apt_stp_type")
    if stp_type:
        exterior_cost += {"stp_only": 1000000, "stp_rwh": 1500000,
                          "stp_wtp_rwh": 2500000}.get(stp_type, 1000000)

    sec = form.get("apt_security_level", "")
    if sec:
        exterior_cost += {"basic": 150000, "standard": total_units * 10000,
                          "smart": total_units * 22000}.get(sec, 0)

    exterior_cost += _safe_float(form.get("apt_solar_kw"), 0) * 65000

    # Miscellaneous
    misc_cost = sqft * floors * MISC_APT_PER_SQFT

    return {
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


# ─────────────────────────────────────────────────────────────────
#  COST TIER SCALING
# ─────────────────────────────────────────────────────────────────

TIER_FACTOR = {"low": 0.75, "medium": 1.00, "high": 1.40}


def _build_cost_tiers(base_breakdown, scope):
    labour_pct = 0.22 if scope == "material_and_labour" else 0.0
    all_costs  = {}
    for tier, fac in TIER_FACTOR.items():
        stage_costs = {k: round(v * fac, 0) for k, v in base_breakdown.items()}
        mat  = sum(stage_costs.values())
        lab  = round(mat * labour_pct, 0)
        oth  = round(mat * 0.025, 0)
        all_costs[tier] = {
            "material_cost":   round(mat, 0),
            "labor_cost":      round(lab, 0),
            "other_costs":     round(oth, 0),
            "total_cost":      round(mat + lab + oth, 0),
            "stage_breakdown": stage_costs,
        }
    return all_costs


# ─────────────────────────────────────────────────────────────────
#  MATERIAL QUANTITIES / BOQ
# ─────────────────────────────────────────────────────────────────

def _build_quantities(sqft, floors, rooms, bathrooms, ceiling_ht, form, prefix=""):
    p = prefix

    def f(key, default=None):
        return form.get(f"{p}{key}", form.get(key, default))

    slab_fac  = SLAB_THICKNESS_FACTOR.get(_safe_float(f("slab_thickness", 5), 5.0), 1.0)
    conc_fac  = CONCRETE_GRADE_FACTOR.get(f("concrete_grade", "M20"), 1.0)
    steel_fac = STEEL_GRADE_FACTOR.get(f("steel_grade", "Fe500"), 1.0)
    num_doors   = _safe_int(f("num_doors",   6), 6)
    num_windows = _safe_int(f("num_windows", 8), 8)
    wall_info   = _wall_areas(sqft, floors, ceiling_ht, num_doors, num_windows)
    wm          = WALL_MATERIAL_RATE.get(f("wall_material", "red_clay"),
                                         WALL_MATERIAL_RATE["red_clay"])

    foundation = {
        "cement_bags":      round(sqft * 0.175 * floors * conc_fac * slab_fac, 1),
        "sand_cuft":        round(sqft * 0.525 * floors * slab_fac, 1),
        "aggregate_cuft":   round(sqft * 0.70  * floors * slab_fac, 1),
        "steel_kg":         round(sqft * 3.5   * floors * steel_fac, 1),
        "concrete_blocks":  int(sqft * 2.8 * slab_fac),
        "water_liters":     round(sqft * 18 * floors, 1),
        "waterproofing_kg": round(sqft * 0.18, 1),
    }

    walls = {
        "bricks_or_blocks":      int(wall_info["total_gross"] * wm["bags_per_sqft"] * 4.5),
        "cement_bags":           round(wall_info["total_gross"] * wm["bags_per_sqft"], 1),
        "sand_cuft":             round(wall_info["total_gross"] * wm["bags_per_sqft"] * 2.5, 1),
        "doors":                 num_doors,
        "windows":               num_windows,
        "internal_plaster_sqft": round(wall_info["int_net"], 1),
        "external_plaster_sqft": round(wall_info["ext_net"], 1),
    }

    if prefix == "villa_":
        _floor_type = f("flooring_grade", "italian_marble")
    else:
        _floor_type = f("flooring_type", "vitrified")

    flooring = {
        "cement_bags":               round(sqft * 0.15 * floors * conc_fac * slab_fac, 1),
        "sand_cuft":                 round(sqft * 0.38 * floors * slab_fac, 1),
        "steel_kg":                  round(sqft * 3.04 * floors * steel_fac, 1),
        "aggregate_cuft":            round(sqft * 0.57 * floors * slab_fac, 1),
        "floor_tiles_sqft":          round(sqft * floors * 0.70, 1),
        "bathroom_wall_tiles_sqft":  round(bathrooms * 7 * ceiling_ht * 0.65, 1),
        "shuttering_sqft":           round(sqft * floors * 0.48, 1),
    }

    roofing = {
        "steel_kg":           round(sqft * 4.4  * steel_fac, 1),
        "cement_bags":        round(sqft * 0.22 * conc_fac * slab_fac, 1),
        "sand_cuft":          round(sqft * 0.44 * slab_fac, 1),
        "aggregate_cuft":     round(sqft * 0.66 * slab_fac, 1),
        "waterproofing_sqft": round(sqft / max(floors, 1), 1),
    }

    total_pipe = (bathrooms * 22) + (floors * 50) + 30
    plumbing = {
        "pvc_pipes_meters":  round(total_pipe * 0.40, 1),
        "cpvc_pipes_meters": round(total_pipe * 0.35, 1),
        "gi_pipes_meters":   round(total_pipe * 0.15, 1),
        "water_tank_liters": _safe_int(f("overhead_tank_capacity", 1000), 1000),
        "sump_liters":       _safe_int(f("sump_capacity", 5000), 5000),
        "taps":              _safe_int(f("num_taps",    bathrooms * 4 + 4), bathrooms * 4 + 4),
        "washbasins":        bathrooms,
        "toilets":           bathrooms,
        "kitchen_sink":      1,
        "valves":            bathrooms * 3 + 3,
        "showers":           _safe_int(f("num_showers", bathrooms), bathrooms),
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
        "ac_points":        _safe_int(f("num_ac_points", 0), 0),
    }

    kp_len = _safe_float(f("kitchen_platform_length", 10), 10.0)

    if prefix == "villa_":
        fc_key = form.get("villa_false_ceiling", "no")
    elif prefix == "":
        fc_key = form.get("false_ceiling_yn", "no") or "no"
    else:
        fc_key = form.get("apt_false_ceiling", "none")
    fc_area = _false_ceiling_area(sqft, fc_key)

    finishing = {
        "putty_kg":              round(wall_info["int_net"] * 0.8, 1),
        "primer_liters":         round(wall_info["int_net"] * 0.06, 1),
        "interior_paint_liters": round(wall_info["int_net"] * 0.08, 1),
        "exterior_paint_liters": round(wall_info["ext_net"] * 0.07, 1),
        "false_ceiling_sqft":    round(fc_area, 1),
        "kitchen_platform_sqft": round(kp_len * 2.5, 1),
    }

    carpentry = {
        "plywood_sheets": round(rooms * 3.2, 1),
        "laminate_sqft":  round(rooms * 20, 1),
        "mdf_sheets":     round(rooms * 1.6, 1),
        "wardrobes":      max(1, rooms - 1),
        "hinges":         (rooms * 6) + (bathrooms * 3),
        "handles":        (rooms * 4) + (bathrooms * 2),
    }

    exterior = {
        "car_porch_sqft":       _safe_float(f("car_porch_sqft"), 200),
        "boundary_wall_rft":    _safe_float(f("boundary_rft"), 0),
        "garden_sqft":          _safe_float(f("garden_sqft"), 0),
        "sump_capacity_liters": _safe_int(f("sump_capacity", 5000), 5000),
    }

    miscellaneous = {
        "waterproofing_chem_kg": round(sqft * 0.12, 1),
        "binding_wire_kg":       round(sqft * 0.04, 1),
        "safety_equipment_sets": max(1, floors),
        "nails_kg":              round(sqft * 0.02, 1),
    }

    return {
        "foundation": foundation, "walls": walls, "flooring": flooring,
        "roofing": roofing, "plumbing": plumbing, "electrical": electrical,
        "finishing": finishing, "carpentry": carpentry, "exterior": exterior,
        "miscellaneous": miscellaneous,
    }


# ─────────────────────────────────────────────────────────────────
#  TIMELINE
# ─────────────────────────────────────────────────────────────────

def _build_timeline(sqft, floors, rooms):
    tl = {
        "foundation": round(sqft / 44,  0),
        "walls":      round(sqft / 36,  0),
        "flooring":   round(sqft / 57,  0),
        "roofing":    round(sqft / 67,  0),
        "plumbing":   round(sqft / 100, 0),
        "electrical": round(sqft / 100, 0),
        "finishing":  round(sqft / 44,  0),
        "carpentry":  round(rooms * 7,  0),
        "exterior":   round(sqft / 167, 0),
    }
    tl["total_days"] = int(sum(tl.values()))
    return tl


# ─────────────────────────────────────────────────────────────────
#  AI REFINEMENT
#  FIX: returns explicit failure signal instead of empty dict,
#       so the caller and UI can show a visible fallback message.
# ─────────────────────────────────────────────────────────────────

AI_FAILURE_RESULT = {
    "rationale":  ("AI refinement unavailable — estimate uses base rate tables "
                   "(March 2026 market prices). Rates may vary ±10–15% by location."),
    "confidence": 0,   # 0 signals failure to the template
}


def _ai_refine_estimate(base_costs, form, sqft, property_type):
    import json, requests
    summary = {
        "sqft": sqft,
        "property_type": property_type,
        "location": form.get("location", "India"),
        "base_total_medium": base_costs.get("medium", {}).get("total_cost", 0),
        "stages": dict(base_costs.get("medium", {}).get("stage_breakdown", {})),
        "key_inputs": {
            "concrete_grade":  (form.get("concrete_grade") or form.get("villa_concrete_grade")
                                or form.get("apt_concrete_grade")),
            "steel_grade":     (form.get("steel_grade") or form.get("villa_steel_grade")
                                or form.get("apt_steel_grade")),
            "soil_condition":  (form.get("soil_condition") or form.get("villa_soil_condition")
                                or form.get("apt_soil_condition")),
            "foundation_type": (form.get("foundation_type") or form.get("villa_foundation_type")
                                or form.get("apt_foundation_type")),
            "flooring":        (form.get("flooring_type") or form.get("villa_flooring_grade")
                                or form.get("apt_flooring_type")),
            "location_state":  form.get("location_state", ""),
        },
    }
    prompt = (
        f"You are a senior construction cost estimator in India.\n"
        f"Review this estimate for a {property_type} of {sqft} sqft and respond ONLY with JSON.\n\n"
        f"Input:\n{json.dumps(summary, indent=2)}\n\n"
        f"Return EXACTLY this JSON with adjustment factors 0.75-1.35 per stage (1.0=reasonable). "
        f"Include rationale (max 40 words) and confidence 1-10.\n\n"
        f'{{"foundation":1.0,"walls":1.0,"flooring":1.0,"roofing":1.0,"plumbing":1.0,'
        f'"electrical":1.0,"finishing":1.0,"carpentry":1.0,"exterior":1.0,'
        f'"miscellaneous":1.0,"rationale":"...","confidence":8}}'
    )
    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"Content-Type": "application/json"},
            json={"model": "claude-sonnet-4-6", "max_tokens": 512,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=12,
        )
        if resp.status_code == 200:
            data = resp.json()
            text = "".join(b.get("text", "") for b in data.get("content", [])
                           if b.get("type") == "text")
            text = text.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
            parsed = json.loads(text)
            # Validate it has at least a rationale key
            if "rationale" in parsed:
                return parsed
    except Exception as e:
        print(f"[AI refine] skipped: {e}")

    # FIX: explicit failure result — not a silent empty dict
    return AI_FAILURE_RESULT.copy()


def _apply_ai_factors(costs, factors):
    # If AI failed (confidence == 0), skip applying factors — base rates are unchanged
    if not factors or factors.get("confidence", 1) == 0:
        return costs
    stage_keys = ["foundation", "walls", "flooring", "roofing", "plumbing",
                  "electrical", "finishing", "carpentry", "exterior", "miscellaneous"]
    for tier in costs:
        for stage in stage_keys:
            fac = max(0.75, min(1.35, float(factors.get(stage, 1.0))))
            costs[tier]["stage_breakdown"][stage] = round(
                costs[tier]["stage_breakdown"][stage] * fac, 0)
        mat = sum(costs[tier]["stage_breakdown"].values())
        lab = round(mat * 0.22, 0) if costs[tier]["labor_cost"] > 0 else 0
        oth = round(mat * 0.025, 0)
        costs[tier].update({
            "material_cost": round(mat, 0),
            "labor_cost":    lab,
            "other_costs":   oth,
            "total_cost":    round(mat + lab + oth, 0),
        })
    return costs


# ─────────────────────────────────────────────────────────────────
#  PUBLIC ENTRY POINT
# ─────────────────────────────────────────────────────────────────

def calculate_materials_and_cost(square_feet, rooms, floors, bathrooms,
                                 budget_range, form: Optional[dict] = None):
    if form is None:
        form = {}

    sqft      = float(square_feet)
    plot_area = _safe_float(form.get("plot_area"), sqft * 1.3)
    prop_type = form.get("property_type", "residential")
    scope     = form.get("estimate_scope", "material_only")

    if prop_type == "apartment":
        try:
            floors = max(1, int(form.get("apt_total_floors", floors) or floors))
            if floors == 99:
                floors = 30
        except (ValueError, TypeError):
            floors = max(1, int(floors))
        rooms     = max(1, int(rooms))
        bathrooms = max(1, int(bathrooms))
    elif prop_type == "villa":
        floors    = max(1, _safe_int(form.get("villa_floors",    floors),    int(floors)))
        rooms     = max(1, _safe_int(form.get("villa_rooms",     rooms),     int(rooms)))
        bathrooms = max(1, _safe_int(form.get("villa_bathrooms", bathrooms), int(bathrooms)))
    else:
        floors    = max(1, int(floors))
        rooms     = max(1, int(rooms))
        bathrooms = max(1, int(bathrooms))

    if prop_type == "villa":
        ceiling_ht = _safe_float(
            form.get("villa_ceiling_height") or form.get("ceiling_height"), 12.0)
    elif prop_type == "apartment":
        ceiling_ht = _safe_float(form.get("apt_ceiling_height"), 10.0)
    else:
        ceiling_ht = _safe_float(form.get("ceiling_height"), 10.0)

    if prop_type == "villa":
        base_bd = _calc_residential(form, sqft, plot_area, floors,
                                    bathrooms, rooms, ceiling_ht, prefix="villa_")
    elif prop_type == "apartment":
        base_bd = _calc_apartment(form, sqft, plot_area, floors)
    else:
        base_bd = _calc_residential(form, sqft, plot_area, floors,
                                    bathrooms, rooms, ceiling_ht, prefix="")

    costs = _build_cost_tiers(base_bd, scope)

    ai_factors = _ai_refine_estimate(costs, form, sqft, prop_type)
    costs      = _apply_ai_factors(costs, ai_factors)

    if prop_type == "villa":
        materials = _build_quantities(sqft, floors, rooms, bathrooms,
                                      ceiling_ht, form, prefix="villa_")
    elif prop_type == "apartment":
        bhk1 = _safe_int(form.get("apt_1bhk_count"), 0)
        bhk2 = _safe_int(form.get("apt_2bhk_count"), 0)
        bhk3 = _safe_int(form.get("apt_3bhk_count"), 0)
        total_units = _safe_int(form.get("apt_total_units"), 1)
        total_baths = bhk1 + bhk2 * 2 + bhk3 * 3 or total_units * 2
        avg_baths   = max(1, total_baths // max(total_units, 1))
        apt_rooms   = max(1, (bhk1 + bhk2 * 2 + bhk3 * 3) or total_units * 2)
        materials   = _build_quantities(sqft, floors, apt_rooms,
                                        avg_baths, ceiling_ht, form, prefix="")
    else:
        materials = _build_quantities(sqft, floors, rooms, bathrooms,
                                      ceiling_ht, form, prefix="")

    timeline = _build_timeline(sqft, floors, rooms)

    return {
        "materials":             materials,
        "costs":                 costs,
        "timeline":              timeline,
        "selected_budget":       budget_range,
        "total_materials_count": sum(len(s) for s in materials.values()),
        "ai_rationale":          ai_factors.get("rationale", ""),
        "ai_confidence":         ai_factors.get("confidence", 0),
        "ai_success":            ai_factors.get("confidence", 0) > 0,  # NEW: explicit flag
        "estimate_scope":        scope,
        "property_type":         prop_type,
    }