"""
model_route.py  —  House-Forge 3D Model Viewer Route
=====================================================
Add to your Flask app blueprint (user.py or routes.py):

    from .model_route import model_bp
    app.register_blueprint(model_bp)

Or copy the route function directly into your existing user blueprint.

The route reads a saved Project from the database and passes
all construction parameters to the viewer template as JSON so
Three.js can build the schematic 3D model client-side.

Assumes your Project model has the fields added in create_project_edited.html.
Fields that may not exist yet (new additions) are fetched with getattr(..., default).
"""

import json
import math
from flask import Blueprint, render_template, jsonify, abort
from flask_login import login_required, current_user
from models.user import Project  # adjust import to your project structure

model_bp = Blueprint('model', __name__)


def _safe(obj, attr, default=None):
    """Safely get an attribute that may not exist on older records."""
    return getattr(obj, attr, default) or default


def project_to_model_data(project):
    """
    Convert a Project ORM object into a flat dict that the
    Three.js viewer consumes. All geometry is derived here —
    the frontend only renders, never calculates.
    """
    ptype = _safe(project, 'property_type', 'residential')

    # ── Shared geometry inputs ──────────────────────────────────────
    built_sqft  = float(_safe(project, 'square_feet', 1500) or 1500)
    plot_sqft   = float(_safe(project, 'plot_area',   2400) or 2400)
    budget      = _safe(project, 'budget_range', 'medium')

    # Derive approximate building footprint (sqft per floor)
    # We don't have floor dimensions so we infer a square-ish footprint
    floors      = int(_safe(project, 'floors', 1) or 1)
    footprint   = built_sqft / max(floors, 1)   # sqft per floor

    # Convert sqft → metres for Three.js (1 sqft ≈ 0.0929 m²)
    # We work in metres. 1 unit in Three.js = 1 metre.
    fp_side     = math.sqrt(footprint * 0.0929)  # metres, square footprint
    plot_side   = math.sqrt(plot_sqft  * 0.0929)

    # ── Type-specific ───────────────────────────────────────────────
    if ptype == 'residential':
        data = _build_residential(project, fp_side, plot_side, floors, budget)

    elif ptype == 'villa':
        data = _build_villa(project, fp_side, plot_side, budget)

    elif ptype == 'apartment':
        data = _build_apartment(project, fp_side, plot_side, budget)

    else:
        data = _build_residential(project, fp_side, plot_side, floors, budget)

    data.update({
        'project_id':    project.id,
        'project_title': _safe(project, 'title', 'My Project'),
        'property_type': ptype,
        'plot_side':     round(plot_side, 2),
        'budget':        budget,
    })
    return data


# ──────────────────────────────────────────────────────────────────────
#  RESIDENTIAL
# ──────────────────────────────────────────────────────────────────────
def _build_residential(project, fp_side, plot_side, floors, budget):
    ceiling_h   = float(_safe(project, 'ceiling_height', 10) or 10) * 0.3048  # ft→m
    slab_h      = 0.15  # 5 inch slab in metres
    floor_total = ceiling_h + slab_h
    roof_type   = _safe(project, 'villa_roof_type', 'flat_rcc')  # reuse field
    staircase   = _safe(project, 'staircase_type', 'rcc')
    flooring    = _safe(project, 'flooring_type', 'vitrified')
    wall_mat    = _safe(project, 'wall_material', 'red_clay')
    plaster     = _safe(project, 'plaster_type', '12mm_cm')
    int_paint   = _safe(project, 'internal_paint_quality', 'emulsion')
    ext_paint   = _safe(project, 'external_paint_quality', 'weathershield')
    false_ceil  = _safe(project, 'false_ceiling_yn', 'no')
    pipe_mat    = _safe(project, 'pipe_material', 'cpvc')
    sanitary    = _safe(project, 'sanitary_grade', 'standard')
    wiring      = _safe(project, 'wiring_type', 'fr_pvc')
    num_baths   = int(_safe(project, 'bathrooms', 2) or 2)
    num_ac      = int(_safe(project, 'num_ac_points', 0) or 0)

    # Add-ons
    has_porch    = True   # default on
    has_sump     = True   # default on
    has_boundary = False  # checked by JS
    has_garden   = False

    # Build floor list for animation
    floor_list = []
    for i in range(floors):
        y_base = i * floor_total
        floor_list.append({
            'index':  i,
            'y':      round(y_base, 3),
            'height': round(ceiling_h, 3),
            'label':  'Ground Floor' if i == 0 else f'Floor {i}',
            'zones': _residential_floor_zones(fp_side, ceiling_h, i, floors,
                                               flooring, wall_mat, int_paint,
                                               pipe_mat, sanitary, wiring, num_baths, num_ac)
        })

    # Roof
    roof = _make_roof(fp_side, floors * floor_total, roof_type)

    # Car porch (offset to front, 30% of building width)
    porch = None
    if has_porch:
        porch_w = fp_side * 0.6
        porch_d = fp_side * 0.4
        porch = {
            'x': fp_side / 2 + porch_d / 2,
            'z': 0,
            'w': porch_d,
            'd': porch_w,
            'h': ceiling_h * 0.6,
            'color': 0xB5804F,
            'label': 'Car Porch',
            'cost_hint': '₹1.5–4L depending on size & finish',
            'zone': 'finishes'
        }

    # Boundary wall
    boundary = None
    boundary_rft = float(_safe(project, 'boundary_rft', 0) or 0)
    if boundary_rft > 0:
        boundary = {
            'plot_side': round(plot_side, 2),
            'height': 1.83,  # 6 ft in metres
            'color': 0x8C5E35,
            'label': 'Boundary Wall',
            'cost_hint': f'~₹{int(boundary_rft * 1800):,}–₹{int(boundary_rft * 3500):,}',
            'zone': 'structure'
        }

    return {
        'floors':     floor_list,
        'roof':       roof,
        'fp_side':    round(fp_side, 2),
        'floor_h':    round(floor_total, 3),
        'porch':      porch,
        'boundary':   boundary,
        'has_sump':   has_sump,
        'ext_paint':  ext_paint,
        'false_ceil': false_ceil,
        'staircase':  staircase,
    }


def _residential_floor_zones(fp, h, floor_idx, total_floors,
                              flooring, wall_mat, paint,
                              pipe, sanitary, wiring, baths, ac_pts):
    """Return coloured zone boxes for one residential floor."""
    zones = []

    # Structure core (columns + slab) — grey
    zones.append({
        'type': 'box', 'zone': 'structure',
        'x': 0, 'y': 0, 'z': 0,
        'w': fp, 'h': 0.15, 'd': fp,
        'color': 0x9E9E9E,
        'label': 'RCC Slab',
        'cost_hint': 'Concrete + steel — largest single cost line',
        'opacity': 1.0
    })

    # Wall shell — warm grey (finishes)
    wall_colors = {'red_clay': 0xC49A6C, 'aac_blocks': 0xD4C4B0, 'fly_ash': 0xBFB5A0}
    wall_col = wall_colors.get(wall_mat, 0xC49A6C)
    wall_t = 0.23  # 9-inch wall in metres
    # Front wall
    zones.append({'type': 'wall', 'zone': 'finishes',
                  'x': 0, 'y': h/2, 'z': -fp/2,
                  'w': fp, 'h': h, 'd': wall_t,
                  'color': wall_col, 'label': f'Masonry ({wall_mat.replace("_"," ").title()})',
                  'cost_hint': '₹180–350/sqft of wall area', 'opacity': 0.92})

    # Interior flooring slab face — warm (finishes)
    floor_colors = {'vitrified': 0xF5F0E8, 'marble': 0xFFF8F0, 'granite': 0x808080,
                    'ceramic': 0xE8DDD0, 'hardwood': 0x8B5E3C}
    floor_col = floor_colors.get(flooring, 0xF5F0E8)
    zones.append({'type': 'box', 'zone': 'finishes',
                  'x': 0, 'y': 0.08, 'z': 0,
                  'w': fp - wall_t*2, 'h': 0.012, 'd': fp - wall_t*2,
                  'color': floor_col,
                  'label': f'Flooring ({flooring.replace("_"," ").title()})',
                  'cost_hint': _flooring_cost(flooring), 'opacity': 1.0})

    # Paint indicator strip (top of walls) — warm accent
    paint_colors = {'emulsion': 0xFFF9F0, 'luxury': 0xFFF3E0, 'texture': 0xFFE0B2}
    paint_col = paint_colors.get(paint, 0xFFF9F0)
    zones.append({'type': 'box', 'zone': 'finishes',
                  'x': 0, 'y': h - 0.05, 'z': 0,
                  'w': fp, 'h': 0.08, 'd': fp,
                  'color': paint_col,
                  'label': f'Internal Paint ({paint.replace("_"," ").title()})',
                  'cost_hint': _paint_cost(paint), 'opacity': 0.85})

    # MEP risers — blue strip at back-left corner
    zones.append({'type': 'box', 'zone': 'mep',
                  'x': -fp/2 + 0.3, 'y': h/2, 'z': fp/2 - 0.3,
                  'w': 0.3, 'h': h, 'd': 0.3,
                  'color': 0x1565C0,
                  'label': f'Plumbing Riser ({pipe.upper()})',
                  'cost_hint': '₹120–180/rft CPVC installed', 'opacity': 0.9})

    if ac_pts > 0:
        zones.append({'type': 'box', 'zone': 'mep',
                      'x': fp/2 - 0.3, 'y': h - 0.3, 'z': fp/2 - 0.3,
                      'w': 0.3, 'h': 0.3, 'd': 0.3,
                      'color': 0x0288D1,
                      'label': f'AC Conduit ({ac_pts} points)',
                      'cost_hint': '₹8–15K per AC point wired', 'opacity': 0.9})

    return zones


# ──────────────────────────────────────────────────────────────────────
#  VILLA
# ──────────────────────────────────────────────────────────────────────
def _build_villa(project, fp_side, plot_side, budget):
    floors      = int(_safe(project, 'floors', 2) or 2)
    ceiling_h   = float(_safe(project, 'villa_ceiling_height', 12) or 12) * 0.3048
    slab_h      = 0.14
    floor_total = ceiling_h + slab_h
    roof_type   = _safe(project, 'villa_roof_type', 'flat_rcc')
    flooring    = _safe(project, 'villa_flooring_grade', 'italian_marble')
    wall_mat    = _safe(project, 'villa_wall_material', 'aac_blocks')
    cladding    = _safe(project, 'villa_cladding', 'stone')
    fc_type     = _safe(project, 'villa_false_ceiling', 'partial')
    pipe_mat    = _safe(project, 'villa_pipe_material', 'cpvc')
    wiring      = _safe(project, 'villa_wiring_type', 'lszh')
    num_ac      = int(_safe(project, 'villa_num_ac_points', 0) or 0)
    has_pool    = False  # determined by villa_pool_length
    pool_l      = float(_safe(project, 'pool_length', 0) or 0)
    pool_w      = float(_safe(project, 'pool_width', 0) or 0)
    has_pool    = pool_l > 0 and pool_w > 0
    boundary_rft = float(_safe(project, 'villa_boundary_rft', 0) or 0)
    has_boundary = boundary_rft > 0
    garden_sqft  = float(_safe(project, 'villa_garden_sqft', 0) or 0)
    has_garden   = garden_sqft > 0
    staircase    = _safe(project, 'villa_staircase', 'standard')

    floor_list = []
    for i in range(floors):
        y_base = i * floor_total
        floor_list.append({
            'index': i,
            'y': round(y_base, 3),
            'height': round(ceiling_h, 3),
            'label': 'Ground Floor' if i == 0 else f'Floor {i}',
            'zones': _villa_floor_zones(fp_side, ceiling_h, i, floors,
                                         flooring, wall_mat, cladding,
                                         fc_type, pipe_mat, wiring, num_ac)
        })

    roof = _make_roof(fp_side, floors * floor_total, roof_type)

    pool = None
    if has_pool:
        pool = {
            'x': plot_side / 2 - pool_l * 0.15,
            'z': plot_side / 2 - pool_w * 0.15,
            'w': round(pool_l * 0.3048, 2),  # ft→m
            'd': round(pool_w * 0.3048, 2),
            'h': 1.5,
            'color': 0x29B6F6,
            'label': 'Swimming Pool',
            'cost_hint': f'~₹{int(pool_l * pool_w * 12000):,}–₹{int(pool_l * pool_w * 22000):,}',
            'zone': 'mep'
        }

    boundary = None
    if has_boundary:
        boundary = {
            'plot_side': round(plot_side, 2),
            'height': float(_safe(project, 'villa_boundary_height', 8) or 8) * 0.3048,
            'color': 0x795548,
            'label': 'Boundary Wall',
            'cost_hint': f'~₹{int(boundary_rft * 2500):,}–₹{int(boundary_rft * 5000):,}',
            'zone': 'structure'
        }

    garden = None
    if has_garden:
        garden = {
            'area_sqft': garden_sqft,
            'color': 0x388E3C,
            'label': 'Garden / Landscaping',
            'cost_hint': f'~₹{int(garden_sqft * 80):,}–₹{int(garden_sqft * 300):,}',
            'zone': 'finishes'
        }

    porch = None
    porch_size = _safe(project, 'villa_car_porch_size', '')
    if porch_size:
        porch_areas = {'single': 200, 'double': 400, 'triple': 600}
        porch_sqft  = float(_safe(project, 'villa_car_porch_sqft', 0) or
                            porch_areas.get(porch_size, 300)) * 0.0929
        porch_side  = math.sqrt(porch_sqft)
        porch = {
            'x': fp_side / 2 + porch_side / 2,
            'z': 0,
            'w': porch_side,
            'd': porch_side,
            'h': ceiling_h * 0.5,
            'color': 0xA1887F,
            'label': 'Car Porch / Porte-cochère',
            'cost_hint': '₹3–8L depending on style',
            'zone': 'finishes'
        }

    return {
        'floors':     floor_list,
        'roof':       roof,
        'fp_side':    round(fp_side, 2),
        'floor_h':    round(floor_total, 3),
        'pool':       pool,
        'boundary':   boundary,
        'garden':     garden,
        'porch':      porch,
        'staircase':  staircase,
    }


def _villa_floor_zones(fp, h, floor_idx, total_floors,
                        flooring, wall_mat, cladding,
                        fc_type, pipe, wiring, ac_pts):
    zones = []
    wall_t = 0.23

    # Slab
    zones.append({'type': 'box', 'zone': 'structure',
                  'x': 0, 'y': 0, 'z': 0,
                  'w': fp, 'h': 0.14, 'd': fp,
                  'color': 0x90A4AE,
                  'label': 'Villa RCC Slab (5.5 inch)',
                  'cost_hint': 'M25 concrete + Fe500D steel', 'opacity': 1.0})

    # Luxury flooring
    floor_colors = {
        'italian_marble': 0xFFFDE7, 'premium_granite': 0x78909C,
        'hardwood': 0x795548, 'natural_stone': 0xA1887F
    }
    zones.append({'type': 'box', 'zone': 'finishes',
                  'x': 0, 'y': 0.09, 'z': 0,
                  'w': fp - wall_t*2, 'h': 0.015, 'd': fp - wall_t*2,
                  'color': floor_colors.get(flooring, 0xFFFDE7),
                  'label': f'Flooring — {flooring.replace("_", " ").title()}',
                  'cost_hint': _villa_flooring_cost(flooring), 'opacity': 1.0})

    # External cladding shell
    clad_colors = {'stone': 0xA1887F, 'plaster': 0xD7CCC8,
                   'glass_facade': 0x80D8FF, 'composite': 0x90A4AE}
    clad_col = clad_colors.get(cladding, 0xA1887F)
    zones.append({'type': 'wall', 'zone': 'finishes',
                  'x': 0, 'y': h/2, 'z': -fp/2,
                  'w': fp, 'h': h, 'd': wall_t,
                  'color': clad_col,
                  'label': f'External Cladding — {cladding.replace("_", " ").title()}',
                  'cost_hint': '₹200–600/sqft depending on material', 'opacity': 0.9})

    # False ceiling indicator (if partial or full)
    if fc_type in ('partial', 'full'):
        fc_coverage = 0.35 if fc_type == 'partial' else 0.92
        zones.append({'type': 'box', 'zone': 'finishes',
                      'x': 0, 'y': h - 0.3, 'z': 0,
                      'w': fp * fc_coverage, 'h': 0.05, 'd': fp * fc_coverage,
                      'color': 0xFFF8E1,
                      'label': f'False Ceiling ({fc_type.title()}) — Gypsum Board',
                      'cost_hint': '₹80–150/sqft gypsum installed', 'opacity': 0.8})

    # MEP shaft
    zones.append({'type': 'box', 'zone': 'mep',
                  'x': -fp/2 + 0.4, 'y': h/2, 'z': fp/2 - 0.4,
                  'w': 0.4, 'h': h, 'd': 0.4,
                  'color': 0x0D47A1,
                  'label': f'Plumbing Riser — {pipe.upper()}',
                  'cost_hint': '₹120–180/rft installed', 'opacity': 0.9})

    wiring_colors = {'lszh': 0x1565C0, 'fr_pvc': 0x1976D2, 'armoured': 0x0D47A1}
    zones.append({'type': 'box', 'zone': 'mep',
                  'x': fp/2 - 0.3, 'y': h/2, 'z': fp/2 - 0.3,
                  'w': 0.25, 'h': h * 0.8, 'd': 0.25,
                  'color': wiring_colors.get(wiring, 0x1565C0),
                  'label': f'Electrical Conduit — {wiring.upper()}',
                  'cost_hint': '₹35–55/rft LSZH wiring', 'opacity': 0.9})

    return zones


# ──────────────────────────────────────────────────────────────────────
#  APARTMENT
# ──────────────────────────────────────────────────────────────────────
def _build_apartment(project, fp_side, plot_side, budget):
    total_floors  = int(_safe(project, 'apt_total_floors', 5) or 5)
    if total_floors >= 99:
        total_floors = 30  # sentinel value for 30+
    ceiling_h     = float(_safe(project, 'apt_ceiling_height', 10) or 10) * 0.3048
    slab_h        = 0.125
    floor_total   = ceiling_h + slab_h
    parking_type  = _safe(project, 'apt_parking_type', 'open')
    has_basement  = parking_type in ('basement_1', 'basement_2')
    basement_lvls = 2 if parking_type == 'basement_2' else 1 if has_basement else 0
    has_stilt     = parking_type == 'stilt'
    wall_mat      = _safe(project, 'apt_wall_material', 'aac_blocks')
    facade_type   = _safe(project, 'apt_facade_type', 'plaster_paint')
    flooring      = _safe(project, 'apt_flooring_type', 'vitrified')
    int_paint     = _safe(project, 'apt_internal_paint', 'emulsion')
    fc_type       = _safe(project, 'apt_false_ceiling', 'none')
    lifts         = int(_safe(project, 'apt_lifts', 2) or 2)
    pool_type     = _safe(project, 'apt_pool', 'none')
    has_pool      = pool_type != 'none'
    clubhouse     = _safe(project, 'apt_clubhouse', 'none')
    has_clubhouse = clubhouse != 'none'
    total_units   = int(_safe(project, 'apt_total_units', 24) or 24)

    floor_list = []

    # Basement floors (below grade)
    for b in range(basement_lvls):
        y_base = -(b + 1) * (2.8 + slab_h)
        floor_list.append({
            'index': -(b + 1),
            'y': round(y_base, 3),
            'height': 2.8,
            'label': f'Basement {b + 1} — Parking',
            'zones': _apt_basement_zones(fp_side, 2.8),
            'animate_delay': 0  # basements shown immediately
        })

    # Stilt floor
    stilt_y = 0
    if has_stilt:
        floor_list.append({
            'index': 0,
            'y': 0,
            'height': 2.4,
            'label': 'Stilt Floor — Parking',
            'zones': _apt_stilt_zones(fp_side, 2.4),
            'animate_delay': 0
        })
        stilt_y = 2.4 + slab_h

    # Regular floors
    for i in range(total_floors):
        y_base = stilt_y + i * floor_total
        floor_list.append({
            'index': i + 1,
            'y': round(y_base, 3),
            'height': round(ceiling_h, 3),
            'label': 'Ground Floor' if i == 0 else f'Floor {i}',
            'zones': _apt_floor_zones(fp_side, ceiling_h, i, total_floors,
                                       flooring, wall_mat, facade_type,
                                       int_paint, fc_type, lifts)
        })

    roof = _make_roof(fp_side, stilt_y + total_floors * floor_total, 'flat_rcc')

    # Lift core — visible on all floors as a protruding shaft
    lift_core = None
    if lifts > 0:
        core_w = 0.25 + lifts * 1.2
        total_h = stilt_y + total_floors * floor_total
        lift_core = {
            'x': fp_side / 2 - core_w / 2 - 0.1,
            'z': 0,
            'w': core_w,
            'd': 1.8,
            'h': total_h + 1.5,  # protrudes above roof
            'color': 0x546E7A,
            'label': f'Lift / Elevator Shaft ({lifts} lifts)',
            'cost_hint': f'~₹{lifts * 2500000:,}–₹{lifts * 5000000:,} per lift installed',
            'zone': 'mep'
        }

    pool = None
    if has_pool:
        pool_dims = {'small': (6.1, 9.1), 'standard': (9.1, 12.2), 'lap_pool': (7.6, 25)}
        pw, pl = pool_dims.get(pool_type, (6.1, 9.1))
        pool = {
            'x': -plot_side / 2 + pl / 2 + 2,
            'z': plot_side / 2 - pw / 2 - 2,
            'w': round(pl, 2),
            'd': round(pw, 2),
            'h': 1.5,
            'color': 0x29B6F6,
            'label': f'Shared Pool — {pool_type.replace("_", " ").title()}',
            'cost_hint': '₹20–60L for compound pool',
            'zone': 'mep'
        }

    clubhouse_block = None
    if has_clubhouse:
        cb_sizes = {'basic': 3.5, 'standard': 5.5, 'full': 8.0}
        cb_side = cb_sizes.get(clubhouse, 4.0)
        clubhouse_block = {
            'x': -plot_side / 2 + cb_side / 2 + 2,
            'z': -plot_side / 2 + cb_side / 2 + 2,
            'w': cb_side,
            'd': cb_side,
            'h': ceiling_h * 1.2,
            'color': 0xB5804F,
            'label': f'Clubhouse — {clubhouse.title()}',
            'cost_hint': '₹800–1500/sqft for clubhouse build',
            'zone': 'finishes'
        }

    return {
        'floors':          floor_list,
        'roof':            roof,
        'fp_side':         round(fp_side, 2),
        'floor_h':         round(floor_total, 3),
        'lift_core':       lift_core,
        'pool':            pool,
        'clubhouse_block': clubhouse_block,
        'has_basement':    has_basement,
        'basement_levels': basement_lvls,
        'has_stilt':       has_stilt,
        'total_units':     total_units,
        'total_floors':    total_floors,
    }


def _apt_basement_zones(fp, h):
    return [
        {'type': 'box', 'zone': 'structure',
         'x': 0, 'y': h/2, 'z': 0,
         'w': fp, 'h': h, 'd': fp,
         'color': 0x455A64,
         'label': 'Basement Parking Level',
         'cost_hint': 'Includes excavation + retaining walls + waterproofing',
         'opacity': 0.75},
        {'type': 'box', 'zone': 'mep',
         'x': fp/2 - 0.5, 'y': h/2, 'z': 0,
         'w': 0.4, 'h': h * 0.8, 'd': fp * 0.5,
         'color': 0x0288D1,
         'label': 'Basement Drainage + Sump',
         'cost_hint': 'CO sensors + mechanical ventilation', 'opacity': 0.8},
    ]


def _apt_stilt_zones(fp, h):
    return [
        {'type': 'box', 'zone': 'structure',
         'x': 0, 'y': 0, 'z': 0,
         'w': fp, 'h': 0.12, 'd': fp,
         'color': 0x78909C,
         'label': 'Stilt Slab',
         'cost_hint': 'Stilt columns add ~8% to structural cost', 'opacity': 1.0},
    ]


def _apt_floor_zones(fp, h, floor_idx, total_floors,
                      flooring, wall_mat, facade, int_paint, fc_type, lifts):
    zones = []
    wall_t = 0.23

    # Slab
    zones.append({'type': 'box', 'zone': 'structure',
                  'x': 0, 'y': 0, 'z': 0,
                  'w': fp, 'h': 0.125, 'd': fp,
                  'color': 0x90A4AE,
                  'label': 'RCC Slab (5 inch)',
                  'cost_hint': 'Multiplied by total floor count', 'opacity': 1.0})

    # Facade shell
    facade_colors = {
        'plaster_paint': 0xECEFF1, 'texture_paint': 0xD7CCC8,
        'acp_cladding': 0xB0BEC5, 'stone_cladding': 0xA1887F,
        'glass_curtain': 0x80D8FF
    }
    facade_col = facade_colors.get(facade, 0xECEFF1)
    zones.append({'type': 'wall', 'zone': 'finishes',
                  'x': 0, 'y': h/2, 'z': -fp/2,
                  'w': fp, 'h': h, 'd': wall_t,
                  'color': facade_col,
                  'label': f'Façade — {facade.replace("_", " ").title()}',
                  'cost_hint': '₹80–2500/sqft depending on type', 'opacity': 0.88})

    # Interior flooring
    floor_colors = {'vitrified': 0xF5F0E8, 'ceramic': 0xE8DDD0,
                    'marble': 0xFFF8F0, 'granite': 0x9E9E9E, 'hardwood': 0x8B5E3C}
    zones.append({'type': 'box', 'zone': 'finishes',
                  'x': 0, 'y': 0.08, 'z': 0,
                  'w': fp - wall_t*2, 'h': 0.01, 'd': fp - wall_t*2,
                  'color': floor_colors.get(flooring, 0xF5F0E8),
                  'label': f'Flooring — {flooring.replace("_", " ").title()}',
                  'cost_hint': _flooring_cost(flooring), 'opacity': 1.0})

    # False ceiling
    if fc_type in ('partial', 'full'):
        fc_w = (fp - wall_t*2) * (0.4 if fc_type == 'partial' else 0.9)
        zones.append({'type': 'box', 'zone': 'finishes',
                      'x': 0, 'y': h - 0.25, 'z': 0,
                      'w': fc_w, 'h': 0.04, 'd': fc_w,
                      'color': 0xFFF9E6,
                      'label': f'False Ceiling ({fc_type.title()})',
                      'cost_hint': '₹80–150/sqft per flat × unit count', 'opacity': 0.8})

    # MEP column at corner
    zones.append({'type': 'box', 'zone': 'mep',
                  'x': -fp/2 + 0.3, 'y': h/2, 'z': fp/2 - 0.3,
                  'w': 0.25, 'h': h, 'd': 0.25,
                  'color': 0x1565C0,
                  'label': 'Plumbing / Electrical Riser',
                  'cost_hint': 'Common riser serving all flats on this level', 'opacity': 0.9})

    return zones


# ──────────────────────────────────────────────────────────────────────
#  SHARED HELPERS
# ──────────────────────────────────────────────────────────────────────
def _make_roof(fp_side, base_y, roof_type):
    if roof_type == 'sloped_tiled':
        return {'type': 'pyramid', 'base_y': round(base_y, 3),
                'fp_side': round(fp_side, 2), 'peak_h': round(fp_side * 0.28, 2),
                'color': 0xB5804F, 'label': 'Sloped Tiled Roof',
                'cost_hint': '+15% concrete + clay/concrete tiles', 'zone': 'finishes'}
    elif roof_type == 'decorative_pergola':
        return {'type': 'pergola', 'base_y': round(base_y, 3),
                'fp_side': round(fp_side, 2), 'height': 0.6,
                'color': 0x8C5E35, 'label': 'Decorative Pergola',
                'cost_hint': 'Steel posts + timber lattice — structural + aesthetic', 'zone': 'finishes'}
    else:
        return {'type': 'flat', 'base_y': round(base_y, 3),
                'fp_side': round(fp_side * 1.04, 2), 'h': 0.18,
                'color': 0x90A4AE, 'label': 'Flat RCC Roof Slab + Waterproofing',
                'cost_hint': '₹50–120/sqft waterproofing on terrace area', 'zone': 'structure'}


def _flooring_cost(f):
    costs = {'vitrified': '₹60–120/sqft', 'marble': '₹150–350/sqft',
             'granite': '₹120–280/sqft', 'ceramic': '₹40–80/sqft',
             'hardwood': '₹200–500/sqft'}
    return costs.get(f, '₹60–120/sqft')


def _villa_flooring_cost(f):
    costs = {'italian_marble': '₹350–800/sqft', 'premium_granite': '₹200–400/sqft',
             'hardwood': '₹300–600/sqft', 'natural_stone': '₹250–500/sqft'}
    return costs.get(f, '₹350–800/sqft')


def _paint_cost(p):
    costs = {'emulsion': '₹18–28/sqft internal', 'luxury': '₹30–45/sqft internal',
             'texture': '₹50–90/sqft internal'}
    return costs.get(p, '₹18–28/sqft')


# ──────────────────────────────────────────────────────────────────────
#  FLASK ROUTE
# ──────────────────────────────────────────────────────────────────────
@model_bp.route('/project/<int:project_id>/model')
@login_required
def view_model(project_id):
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        abort(403)
    model_data = project_to_model_data(project)
    return render_template(
        'view_model.html',
        project=project,
        model_data_json=json.dumps(model_data)
    )


@model_bp.route('/project/<int:project_id>/model/data')
@login_required
def model_data_api(project_id):
    """JSON endpoint — useful for debugging or future AJAX refresh."""
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        abort(403)
    return jsonify(project_to_model_data(project))