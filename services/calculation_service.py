def calculate_materials_and_cost(square_feet, rooms, floors, bathrooms, budget_range):
    """
    Construction material calculator
    Realistic timeline: ~8-10 months for 2000 sq ft building
    """
    
    # Quality factors
    quality_factors = {'low': 0.40, 'medium': 0.50, 'high': 0.60}
    quality = quality_factors.get(budget_range, 0.50)
    
    # ========== STAGE 1: FOUNDATION MATERIALS ==========
    foundation = {
        'cement_bags': round((square_feet * 0.175 * floors) * quality, 2),
        'sand_cuft': round((square_feet * 0.525 * floors) * quality, 2),
        'aggregate_cuft': round((square_feet * 0.70 * floors) * quality, 2),
        'steel_kg': round((square_feet * 3.5 * floors) * quality, 2),
        'concrete_blocks': int((square_feet * 2.8) * quality),
        'water_liters': round(square_feet * 18 * floors, 2),
        'waterproofing_kg': round(square_feet * 0.175, 2)
    }
    
    # ========== STAGE 2: WALL CONSTRUCTION ==========
    walls = {
        'bricks': int((square_feet * 20 * floors) * quality),
        'cement_bags': round((square_feet * 0.12 * floors) * quality, 2),
        'sand_cuft': round((square_feet * 0.32 * floors) * quality, 2),
        'aac_blocks': int((square_feet * 6) * quality) if budget_range != 'low' else 0,
        'steel_mesh_kg': round((square_feet * 0.8 * floors) * quality, 2)
    }
    
    # ========== STAGE 3: FLOORING & SLAB ==========
    flooring = {
        'cement_bags': round((square_feet * 0.152 * floors) * quality, 2),
        'sand_cuft': round((square_feet * 0.38 * floors) * quality, 2),
        'steel_kg': round((square_feet * 3.04 * floors) * quality, 2),
        'aggregate_cuft': round((square_feet * 0.57 * floors) * quality, 2),
        'tiles_sqft': round(square_feet * floors * 0.70, 2),
        'marble_sqft': round(square_feet * 0.08, 2) if budget_range == 'high' else 0,
        'shuttering_sqft': round(square_feet * floors * 0.48, 2)
    }
    
    # ========== STAGE 4: ROOF CONSTRUCTION ==========
    roofing = {
        'steel_kg': round((square_feet * 4.44) * quality, 2),
        'cement_bags': round((square_feet * 0.222) * quality, 2),
        'sand_cuft': round((square_feet * 0.444) * quality, 2),
        'aggregate_cuft': round((square_feet * 0.666) * quality, 2),
        'waterproofing_kg': round(square_feet * 0.296, 2),
        'roofing_sheets_sqft': round(square_feet * 0.407, 2),
        'clay_tiles': int(square_feet * 4.2) if budget_range == 'high' else 0
    }
    
    # ========== STAGE 5: PLUMBING ==========
    plumbing = {
        'pvc_pipes_meters': round((bathrooms * 22.5) + (floors * 45), 2),
        'cpvc_pipes_meters': round(bathrooms * 13.5, 2),
        'gi_pipes_meters': round(floors * 9, 2),
        'water_tank_liters': 500 * floors,
        'taps': bathrooms * 2 + rooms,
        'washbasin': bathrooms,
        'toilets': bathrooms,
        'kitchen_sink': 1,
        'valves': bathrooms * 3 + 3,
        'septic_tank': 1
    }
    
    # ========== STAGE 6: ELECTRICAL ==========
    electrical = {
        'wiring_meters': round(square_feet * floors * 2.5, 2),
        'switches': rooms * 3 + bathrooms * 2,
        'sockets': rooms * 4 + bathrooms * 2,
        'fans': rooms + 1,
        'lights': rooms * 2 + bathrooms + 3,
        'mcb_breakers': 6 + (floors * 2),
        'distribution_box': floors,
        'conduits_meters': round(square_feet * 1.5, 2)
    }
    
    # ========== STAGE 7: FINISHING ==========
    finishing = {
        'putty_kg': round((square_feet * 2) * 0.21, 2),
        'primer_liters': round((square_feet * 2) * 0.063, 2),
        'paint_liters': round((square_feet * 2) * 0.084, 2),
        'wall_tiles_sqft': round((bathrooms * 42) + 34, 2),
        'floor_tiles_sqft': round(square_feet * floors * 0.462, 2),
        'doors': rooms + bathrooms + 1,
        'windows': rooms * 2 + bathrooms
    }
    
    # ========== STAGE 8: CARPENTRY & INTERIOR ==========
    carpentry = {
        'plywood_sheets': round(rooms * 3.2 * quality, 2),
        'laminate_sqft': round(rooms * 20 * quality, 2),
        'mdf_sheets': round(rooms * 1.6 * quality, 2),
        'modular_kitchen_ft': 10 if rooms >= 3 else 6,
        'wardrobes': max(1, rooms - 2),
        'hinges': (rooms * 6) + (bathrooms * 3),
        'handles': (rooms * 4) + (bathrooms * 2)
    }
    
    # ========== STAGE 9: EXTERIOR & LANDSCAPING ==========
    exterior = {
        'paving_blocks_sqft': round(square_feet * 0.105, 2),
        'garden_soil_cuft': round(square_feet * 0.07, 2),
        'boundary_wall_ft': round((square_feet ** 0.5) * 1.4, 2),
        'gate': 1,
        'grills_kg': round(floors * 17.5, 2)
    }
    
    # ========== STAGE 10: MISCELLANEOUS ==========
    miscellaneous = {
        'waterproofing_chem_kg': round(square_feet * 0.12, 2),
        'insulation_sqft': round(square_feet * 0.20, 2),
        'nails_kg': round(square_feet * 0.02, 2),
        'binding_wire_kg': round(square_feet * 0.04, 2),
        'safety_equipment_sets': max(1, floors)
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
    
    # ========== FURTHER REDUCED COST CALCULATION ==========
    # Rates reduced by an additional ~25% from previous version
    
    stage_prices = {
        'low': {
            'foundation': 82,  'walls': 67,  'flooring': 101,
            'roofing': 118, 'plumbing': 61,  'electrical': 51,
            'finishing': 74,  'carpentry': 135, 'exterior': 51,
            'miscellaneous': 34
        },
        'medium': {
            'foundation': 120, 'walls': 94,  'flooring': 152,
            'roofing': 171, 'plumbing': 94,  'electrical': 85,
            'finishing': 118, 'carpentry': 220, 'exterior': 85,
            'miscellaneous': 51
        },
        'high': {
            'foundation': 172, 'walls': 138, 'flooring': 220,
            'roofing': 242, 'plumbing': 145, 'electrical': 138,
            'finishing': 190, 'carpentry': 321, 'exterior': 138,
            'miscellaneous': 85
        }
    }
    
    # Calculate costs for all budget types
    all_costs = {}
    
    for budget_type in ['low', 'medium', 'high']:
        stage_costs = {}
        total_material_cost = 0
        
        for stage_name in all_materials.keys():
            stage_cost = square_feet * floors * stage_prices[budget_type][stage_name]
            stage_costs[stage_name] = round(stage_cost, 2)
            total_material_cost += stage_cost
        
        # Labor cost: 18% of material cost
        labor_cost = total_material_cost * 0.18
        
        # Other costs: 2.5% (permits, inspections)
        other_costs = total_material_cost * 0.025
        
        total_cost = total_material_cost + labor_cost + other_costs
        
        all_costs[budget_type] = {
            'material_cost': round(total_material_cost, 2),
            'labor_cost': round(labor_cost, 2),
            'other_costs': round(other_costs, 2),
            'total_cost': round(total_cost, 2),
            'stage_breakdown': stage_costs
        }
    
    # ========== REALISTIC TIMELINE ==========
    # Calibrated so 2000 sq ft = ~270 days (~9 months)
    # Formula: days = square_feet / divisor  (per stage)
    timeline = {
        'foundation':  round(square_feet / 44,  0),   # ~45 days for 2000 sqft
        'walls':       round(square_feet / 36,  0),   # ~55 days
        'flooring':    round(square_feet / 57,  0),   # ~35 days
        'roofing':     round(square_feet / 67,  0),   # ~30 days
        'plumbing':    round(square_feet / 100, 0),   # ~20 days
        'electrical':  round(square_feet / 100, 0),   # ~20 days
        'finishing':   round(square_feet / 44,  0),   # ~45 days
        'carpentry':   round(rooms * 7,         0),   # ~28 days for 4 rooms
        'exterior':    round(square_feet / 167, 0),   # ~12 days
        'total_days':  0
    }
    timeline['total_days'] = int(sum(v for k, v in timeline.items() if k != 'total_days'))
    
    return {
        'materials': all_materials,
        'costs': all_costs,
        'timeline': timeline,
        'selected_budget': budget_range,
        'total_materials_count': sum(len(stage) for stage in all_materials.values())
    }


# ========== TESTING FUNCTION ==========
def print_estimation_summary(square_feet, rooms, floors, bathrooms, budget_range):
    """Helper function to test and display estimation results"""
    estimation = calculate_materials_and_cost(square_feet, rooms, floors, bathrooms, budget_range)
    
    print("=" * 80)
    print(f"CONSTRUCTION ESTIMATION - {budget_range.upper()} BUDGET")
    print("=" * 80)
    print(f"\nProject: {square_feet} sq ft | {rooms} rooms | {floors} floors | {bathrooms} bathrooms")
    
    costs = estimation['costs'][budget_range]
    print(f"\n{'COST BREAKDOWN':<40} {'Amount (₹)':<20}")
    print("-" * 80)
    print(f"{'Materials Cost:':<40} ₹{costs['material_cost']:>18,.2f}")
    print(f"{'Labor Cost:':<40} ₹{costs['labor_cost']:>18,.2f}")
    print(f"{'Other Costs:':<40} ₹{costs['other_costs']:>18,.2f}")
    print("-" * 80)
    print(f"{'TOTAL ESTIMATED COST:':<40} ₹{costs['total_cost']:>18,.2f}")
    print("=" * 80)
    
    total_days = estimation['timeline']['total_days']
    months = round(total_days / 30, 1)
    print(f"\nEstimated Timeline: {total_days} days (~{months} months)")
    print(f"Total Material Types: {estimation['total_materials_count']}")
    
    print("\n📅 STAGE-WISE TIMELINE BREAKDOWN:")
    for stage, days in estimation['timeline'].items():
        if stage != 'total_days':
            print(f"   • {stage.capitalize():<20} {int(days)} days")
    
    print(f"\n📦 SAMPLE FOUNDATION MATERIALS:")
    foundation = estimation['materials']['foundation']
    print(f"   • Cement Bags:      {foundation['cement_bags']}")
    print(f"   • Sand (cu ft):     {foundation['sand_cuft']}")
    print(f"   • Steel (kg):       {foundation['steel_kg']}")
    print(f"   • Concrete Blocks:  {foundation['concrete_blocks']}")
    print("=" * 80)


# Test with sample data
if __name__ == "__main__":
    print("\n🏗️  TESTING WITH 2000 SQ FT PROJECT\n")
    print_estimation_summary(
        square_feet=2000,
        rooms=4,
        floors=2,
        bathrooms=3,
        budget_range='low'
    )
    
    print("\n\n📊 COMPARISON WITH ALL BUDGET RANGES:\n")
    estimation = calculate_materials_and_cost(2000, 4, 2, 3, 'low')
    
    print(f"{'Budget Type':<15} {'Material Cost':<22} {'Labor Cost':<20} {'Total Cost':<20}")
    print("-" * 77)
    for budget in ['low', 'medium', 'high']:
        costs = estimation['costs'][budget]
        print(f"{budget.upper():<15} ₹{costs['material_cost']:>18,.2f}   ₹{costs['labor_cost']:>15,.2f}   ₹{costs['total_cost']:>15,.2f}")
    print("-" * 77)
    
    total_days = estimation['timeline']['total_days']
    print(f"\n⏱️  Total Construction Timeline: {total_days} days (~{round(total_days/30, 1)} months)")