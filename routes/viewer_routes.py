from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from firebase_admin import firestore

viewer_bp = Blueprint('viewer', __name__)


def get_db():
    return firestore.client()


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

    # ── Map every form field to viewer_config ──
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
    has_car_porch  = bool(project.get('car_porch_size') or project.get('villa_car_porch_size'))
    has_boundary   = bool(project.get('boundary_rft') or project.get('villa_boundary_rft'))
    has_garden     = bool(project.get('garden_sqft') or project.get('villa_garden_sqft'))
    has_pool       = bool(project.get('pool_length') or
                         (project.get('apt_pool') not in (None, '', 'none')))
    budget_range   = project.get('budget_range', 'medium')
    estimation     = project.get('estimation', {})
    costs          = estimation.get('costs', {})
    tier_costs     = costs.get(budget_range, costs.get('medium', {}))

    viewer_config = {
        'project_id':      project_id,
        'project_title':   project.get('title', 'My Project'),
        'location':        project.get('location', ''),
        'status':          project.get('status', 'planning'),
        'property_type':   prop_type,
        'floors':          floors,
        'rooms':           rooms,
        'bathrooms':       bathrooms,
        'square_feet':     square_feet,
        'plot_area':       plot_area,
        'ceiling_height':  ceiling_height,
        'wall_material':   wall_material,
        'roof_type':       roof_type,
        'facade_type':     (project.get('apt_facade_type') or project.get('villa_cladding') or 'plaster_paint'),
        'door_material':   (project.get('door_material') or project.get('villa_door_material') or 'flush_solid'),
        'window_material': (project.get('window_material') or project.get('villa_window_material') or 'aluminium_sliding'),
        'flooring_type':   (project.get('flooring_type') or project.get('apt_flooring_type') or 'vitrified'),
        'num_doors':       num_doors,
        'num_windows':     num_windows,
        'num_lifts':       num_lifts,
        'apt_total_units': int(project.get('apt_total_units', 1)),
        'apt_parking_type': project.get('apt_parking_type', 'open'),
        'has_car_porch':   has_car_porch,
        'car_porch_size':  (project.get('car_porch_size') or project.get('villa_car_porch_size') or 'single'),
        'has_boundary':    has_boundary,
        'boundary_rft':    float(project.get('boundary_rft') or project.get('villa_boundary_rft') or 0),
        'has_garden':      has_garden,
        'garden_sqft':     float(project.get('garden_sqft') or project.get('villa_garden_sqft') or 0),
        'has_pool':        has_pool,
        'pool_length':     float(project.get('pool_length', 10)),
        'pool_width':      float(project.get('pool_width', 5)),
        'pool_depth':      float(project.get('pool_depth', 5)),
        'budget_range':    budget_range,
        'total_cost':      tier_costs.get('total_cost', 0),
        'material_cost':   tier_costs.get('material_cost', 0),
        'labour_cost':     tier_costs.get('labour_cost', 0),
    }

    return render_template(
        'user/building_3d_viewer.html',
        project=project,
        config=viewer_config,
    )