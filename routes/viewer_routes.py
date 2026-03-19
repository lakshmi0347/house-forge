from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from firebase_admin import firestore

viewer_bp = Blueprint('viewer', __name__)


def get_db():
    return firestore.client()


# ── Exterior colour name → Three.js hex int ──
EXTERIOR_COLOR_HEX = {
    'warm_white':  0xF5F0E8,
    'off_white':   0xEDE8DC,
    'cream':       0xF2E6C8,
    'grey':        0xBBBBBB,
    'terracotta':  0xCC7755,
    'yellow':      0xE8CC66,
}

# ── Roof tile colour name → Three.js hex int ──
ROOF_TILE_COLOR_HEX = {
    'red':   0xAA3322,
    'grey':  0x888888,
    'black': 0x333333,
    'green': 0x446633,
}


@viewer_bp.route('/project/<project_id>/3d-view')
@login_required
def building_3d_view(project_id):
    """
    Reads the real project document from Firestore and passes every
    field the user entered to building_3d_viewer.html as `config`.
    The Jinja2 template injects config as a JS object so Three.js
    uses it to generate the exact 3D geometry for THIS project.
    """
    db = get_db()
    project_doc = db.collection('projects').document(project_id).get()

    if not project_doc.exists:
        flash('Project not found.', 'error')
        return redirect(url_for('user.projects'))

    project = project_doc.to_dict()
    project['id'] = project_id

    # Ownership check
    if project.get('user_id') != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('user.projects'))

    # ── Core structural fields ──
    prop_type      = project.get('property_type', 'residential').lower()
    floors         = int(project.get('floors', 1))
    rooms          = int(project.get('rooms', 2))
    bathrooms      = int(project.get('bathrooms', 1))
    square_feet    = float(project.get('square_feet', 1000))
    plot_area      = float(project.get('plot_area', square_feet * 1.5))
    ceiling_height = float(project.get('ceiling_height') or
                           project.get('villa_ceiling_height') or
                           project.get('apt_ceiling_height') or 10)
    wall_material  = (project.get('wall_material') or
                      project.get('villa_wall_material') or
                      project.get('apt_wall_material') or 'red_clay')
    roof_type      = project.get('villa_roof_type', 'flat_rcc') if prop_type == 'villa' else 'flat_rcc'
    num_doors      = int(project.get('num_doors') or project.get('villa_num_doors') or 4)
    num_windows    = int(project.get('num_windows') or project.get('villa_num_windows') or 6)
    num_lifts      = int(project.get('apt_lifts', 0))
    # FIX: num_staircases was collected in apartment form but never mapped
    num_staircases = int(project.get('apt_staircases', 2))

    has_car_porch  = bool(project.get('car_porch_size') or project.get('villa_car_porch_size'))
    has_boundary   = bool(project.get('boundary_rft') or project.get('villa_boundary_rft'))
    has_garden     = bool(project.get('garden_sqft') or project.get('villa_garden_sqft'))
    has_pool       = bool(project.get('pool_length') or
                         (project.get('apt_pool') not in (None, '', 'none')))

    budget_range   = project.get('budget_range', 'medium')
    estimation     = project.get('estimation', {})
    costs          = estimation.get('costs', {})
    tier_costs     = costs.get(budget_range, costs.get('medium', {}))

    # ── 3D Appearance fields (new) ──
    building_shape     = project.get('building_shape', 'square')

    # Custom dimensions — only set when building_shape == 'rectangular'
    raw_bw = project.get('building_width_ft')
    raw_bd = project.get('building_depth_ft')
    building_width_ft  = float(raw_bw) if raw_bw else None
    building_depth_ft  = float(raw_bd) if raw_bd else None

    # Exterior wall colour chip → hex int (default None = use wall_material lookup)
    ext_color_name     = project.get('exterior_color', '')
    exterior_color_hex = EXTERIOR_COLOR_HEX.get(ext_color_name, None)

    balcony_type       = project.get('balcony_type', 'slab')
    balcony_position   = project.get('balcony_position', 'front')

    ground_floor_use   = project.get('ground_floor_use', 'residential')

    # Roof tile colour — only relevant for sloped roofs
    tile_color_name    = project.get('roof_tile_color', 'red')
    roof_tile_color_hex = ROOF_TILE_COLOR_HEX.get(tile_color_name, ROOF_TILE_COLOR_HEX['red'])

    porch_position     = project.get('porch_position', 'centre')
    garden_position    = project.get('garden_position', 'front')
    pool_position      = project.get('pool_position', 'left')
    landscape_style    = project.get('landscape_style', 'lawn')
    has_solar_panels   = project.get('has_solar_panels', 'none') == 'yes'

    viewer_config = {
        # ── Identity ──
        'project_id':        project_id,
        'project_title':     project.get('title', 'My Project'),
        'location':          project.get('location', ''),
        'status':            project.get('status', 'planning'),

        # ── Core geometry ──
        'property_type':     prop_type,
        'floors':            floors,
        'rooms':             rooms,
        'bathrooms':         bathrooms,
        'square_feet':       square_feet,
        'plot_area':         plot_area,
        'ceiling_height':    ceiling_height,

        # ── Materials (used for colour + panel display) ──
        'wall_material':     wall_material,
        'roof_type':         roof_type,
        'facade_type':       (project.get('apt_facade_type') or project.get('villa_cladding') or 'plaster_paint'),
        'door_material':     (project.get('door_material') or project.get('villa_door_material') or 'flush_solid'),
        'window_material':   (project.get('window_material') or project.get('villa_window_material') or 'aluminium_sliding'),
        'flooring_type':     (project.get('flooring_type') or project.get('apt_flooring_type') or 'vitrified'),

        # ── Counts ──
        'num_doors':         num_doors,
        'num_windows':       num_windows,
        'num_lifts':         num_lifts,
        'num_staircases':    num_staircases,   # FIX: was missing

        # ── Apartment-specific ──
        'apt_total_units':   int(project.get('apt_total_units', 1)),
        'apt_parking_type':  project.get('apt_parking_type', 'open'),

        # ── Add-on booleans ──
        'has_car_porch':     has_car_porch,
        'car_porch_size':    (project.get('car_porch_size') or project.get('villa_car_porch_size') or 'single'),
        'has_boundary':      has_boundary,
        'boundary_rft':      float(project.get('boundary_rft') or project.get('villa_boundary_rft') or 0),
        'has_garden':        has_garden,
        'garden_sqft':       float(project.get('garden_sqft') or project.get('villa_garden_sqft') or 0),
        'has_pool':          has_pool,
        'pool_length':       float(project.get('pool_length', 10)),
        'pool_width':        float(project.get('pool_width', 5)),
        'pool_depth':        float(project.get('pool_depth', 5)),

        # ── Cost display ──
        'budget_range':      budget_range,
        'total_cost':        tier_costs.get('total_cost', 0),
        'material_cost':     tier_costs.get('material_cost', 0),
        'labour_cost':       tier_costs.get('labour_cost', 0),

        # ── 3D Appearance (new) ──
        'building_shape':       building_shape,       # square/rectangular/l_shape/u_shape
        'building_width_ft':    building_width_ft,    # None = auto-derive
        'building_depth_ft':    building_depth_ft,    # None = auto-derive
        'exterior_color_hex':   exterior_color_hex,   # None = use wall_material default
        'balcony_type':         balcony_type,          # none/slab/glass_railing/metal_railing
        'balcony_position':     balcony_position,      # front/front_sides/wrap
        'ground_floor_use':     ground_floor_use,      # residential/stilt_parking/commercial
        'roof_tile_color_hex':  roof_tile_color_hex,   # int hex for sloped roofs
        'porch_position':       porch_position,        # left/centre/right
        'garden_position':      garden_position,       # front/rear/left/right
        'pool_position':        pool_position,         # left/right/rear
        'landscape_style':      landscape_style,       # lawn/tropical/minimal
        'has_solar_panels':     has_solar_panels,      # bool
    }

    return render_template(
        'user/building_3d_viewer.html',
        project=project,
        config=viewer_config,
    )