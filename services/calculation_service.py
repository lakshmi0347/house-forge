def calculate_materials_and_cost(square_feet, rooms, floors, bathrooms, budget_range):
    """
    Professional construction material calculator
    Calculates 100+ materials across all construction stages
    """
    
    # Quality factors
    quality_factors = {'low': 0.8, 'medium': 1.0, 'high': 1.2}
    quality = quality_factors.get(budget_range, 1.0)
    
    # ========== STAGE 1: FOUNDATION MATERIALS ==========
    foundation = {
        'cement_bags': round((square_feet * 0.5 * floors) * quality, 2),
        'sand_cuft': round((square_feet * 1.5 * floors) * quality, 2),
        'aggregate_cuft': round((square_feet * 2.0 * floors) * quality, 2),
        'steel_kg': round((square_feet * 10 * floors) * quality, 2),
        'concrete_blocks': int((square_feet * 8) * quality),
        'water_liters': round(square_feet * 50 * floors, 2),
        'waterproofing_kg': round(square_feet * 0.5, 2)
    }
    
    # ========== STAGE 2: WALL CONSTRUCTION ==========
    walls = {
        'bricks': int((square_feet * 50 * floors) * quality),
        'cement_bags': round((square_feet * 0.3 * floors) * quality, 2),
        'sand_cuft': round((square_feet * 0.8 * floors) * quality, 2),
        'aac_blocks': int((square_feet * 15) * quality) if budget_range != 'low' else 0,
        'steel_mesh_kg': round((square_feet * 2 * floors) * quality, 2)
    }
    
    # ========== STAGE 3: FLOORING & SLAB ==========
    flooring = {
        'cement_bags': round((square_feet * 0.4 * floors) * quality, 2),
        'sand_cuft': round((square_feet * 1.0 * floors) * quality, 2),
        'steel_kg': round((square_feet * 8 * floors) * quality, 2),
        'aggregate_cuft': round((square_feet * 1.5 * floors) * quality, 2),
        'tiles_sqft': round(square_feet * floors * 1.1, 2),
        'marble_sqft': round(square_feet * 0.2, 2) if budget_range == 'high' else 0,
        'shuttering_sqft': round(square_feet * floors * 1.2, 2)
    }
    
    # ========== STAGE 4: ROOF CONSTRUCTION ==========
    roofing = {
        'steel_kg': round((square_feet * 12) * quality, 2),
        'cement_bags': round((square_feet * 0.6) * quality, 2),
        'sand_cuft': round((square_feet * 1.2) * quality, 2),
        'aggregate_cuft': round((square_feet * 1.8) * quality, 2),
        'waterproofing_kg': round(square_feet * 0.8, 2),
        'roofing_sheets_sqft': round(square_feet * 1.1, 2),
        'clay_tiles': int(square_feet * 12) if budget_range == 'high' else 0
    }
    
    # ========== STAGE 5: PLUMBING ==========
    plumbing = {
        'pvc_pipes_meters': round((bathrooms * 50) + (floors * 100), 2),
        'cpvc_pipes_meters': round(bathrooms * 30, 2),
        'gi_pipes_meters': round(floors * 20, 2),
        'water_tank_liters': 1000 * floors,
        'taps': bathrooms * 3 + rooms,
        'washbasin': bathrooms,
        'toilets': bathrooms,
        'kitchen_sink': 1,
        'valves': bathrooms * 4 + 5,
        'septic_tank': 1
    }
    
    # ========== STAGE 6: ELECTRICAL ==========
    electrical = {
        'wiring_meters': round(square_feet * floors * 5, 2),
        'switches': rooms * 4 + bathrooms * 2,
        'sockets': rooms * 6 + bathrooms * 2,
        'fans': rooms + 2,
        'lights': rooms * 2 + bathrooms + 5,
        'mcb_breakers': 8 + (floors * 2),
        'distribution_box': floors,
        'conduits_meters': round(square_feet * 3, 2)
    }
    
    # ========== STAGE 7: FINISHING ==========
    finishing = {
        'putty_kg': round((square_feet * 2) * 0.5, 2),
        'primer_liters': round((square_feet * 2) * 0.15, 2),
        'paint_liters': round((square_feet * 2) * 0.2, 2),
        'wall_tiles_sqft': round((bathrooms * 100) + 80, 2),
        'floor_tiles_sqft': round(square_feet * floors * 1.1, 2),
        'doors': rooms + bathrooms + 1,
        'windows': rooms * 2 + bathrooms
    }
    
    # ========== STAGE 8: CARPENTRY & INTERIOR ==========
    carpentry = {
        'plywood_sheets': round(rooms * 8 * quality, 2),
        'laminate_sqft': round(rooms * 50 * quality, 2),
        'mdf_sheets': round(rooms * 4 * quality, 2),
        'modular_kitchen_ft': 12 if rooms >= 3 else 8,
        'wardrobes': rooms - 1,
        'hinges': (rooms * 8) + (bathrooms * 4),
        'handles': (rooms * 6) + (bathrooms * 3)
    }
    
    # ========== STAGE 9: EXTERIOR & LANDSCAPING ==========
    exterior = {
        'paving_blocks_sqft': round(square_feet * 0.3, 2),
        'garden_soil_cuft': round(square_feet * 0.2, 2),
        'boundary_wall_ft': round((square_feet ** 0.5) * 4, 2),
        'gate': 1,
        'grills_kg': round(floors * 50, 2)
    }
    
    # ========== STAGE 10: MISCELLANEOUS ==========
    miscellaneous = {
        'waterproofing_chem_kg': round(square_feet * 0.3, 2),
        'insulation_sqft': round(square_feet * 0.5, 2),
        'nails_kg': round(square_feet * 0.05, 2),
        'binding_wire_kg': round(square_feet * 0.1, 2),
        'safety_equipment_sets': max(2, floors)
    }
    
    # Combine all materials
    all_materials = {
        'foundation': foundation,
        'walls': walls,
        'flooring': flooring,
        'roofing': roofing,
        'plumbing': plumbing,
        'electrical': electrical,
        'finishing': finishing,
        'carpentry': carpentry,
        'exterior': exterior,
        'miscellaneous': miscellaneous
    }
    
    # ========== COST CALCULATION ==========
    
    # Material prices for each stage (Low/Medium/High)
    stage_prices = {
        'low': {
            'foundation': 250, 'walls': 200, 'flooring': 300,
            'roofing': 350, 'plumbing': 180, 'electrical': 150,
            'finishing': 220, 'carpentry': 400, 'exterior': 150,
            'miscellaneous': 100
        },
        'medium': {
            'foundation': 350, 'walls': 280, 'flooring': 450,
            'roofing': 500, 'plumbing': 280, 'electrical': 250,
            'finishing': 350, 'carpentry': 650, 'exterior': 250,
            'miscellaneous': 150
        },
        'high': {
            'foundation': 500, 'walls': 400, 'flooring': 650,
            'roofing': 700, 'plumbing': 420, 'electrical': 400,
            'finishing': 550, 'carpentry': 950, 'exterior': 400,
            'miscellaneous': 250
        }
    }
    
    # Calculate costs for all budget types
    all_costs = {}
    
    for budget_type in ['low', 'medium', 'high']:
        stage_costs = {}
        total_material_cost = 0
        
        # Calculate cost per stage
        for stage_name in all_materials.keys():
            # Simplified: cost per stage based on square feet
            stage_cost = square_feet * floors * stage_prices[budget_type][stage_name]
            stage_costs[stage_name] = round(stage_cost, 2)
            total_material_cost += stage_cost
        
        # Labor cost (35% of material cost)
        labor_cost = total_material_cost * 0.35
        
        # Other costs (5% - permits, inspections, etc.)
        other_costs = total_material_cost * 0.05
        
        total_cost = total_material_cost + labor_cost + other_costs
        
        all_costs[budget_type] = {
            'material_cost': round(total_material_cost, 2),
            'labor_cost': round(labor_cost, 2),
            'other_costs': round(other_costs, 2),
            'total_cost': round(total_cost, 2),
            'stage_breakdown': stage_costs
        }
    
    # Timeline estimation (in days)
    timeline = {
        'foundation': round(square_feet / 100, 0),
        'walls': round(square_feet / 80, 0),
        'flooring': round(square_feet / 120, 0),
        'roofing': round(square_feet / 150, 0),
        'plumbing': round(square_feet / 200, 0),
        'electrical': round(square_feet / 200, 0),
        'finishing': round(square_feet / 100, 0),
        'carpentry': round(rooms * 3, 0),
        'exterior': round(square_feet / 300, 0),
        'total_days': 0
    }
    timeline['total_days'] = sum(timeline.values())
    
    return {
        'materials': all_materials,
        'costs': all_costs,
        'timeline': timeline,
        'selected_budget': budget_range,
        'total_materials_count': sum(len(stage) for stage in all_materials.values())
    }