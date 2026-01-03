def calculate_materials_and_cost(square_feet, rooms, floors, bathrooms, budget_range):
    """
    Highly optimized construction material calculator
    Reduces material usage by 60-65% for realistic budget estimates
    """
    
    # Significantly reduced quality factors (50% reduction)
    quality_factors = {'low': 0.40, 'medium': 0.50, 'high': 0.60}
    quality = quality_factors.get(budget_range, 0.50)
    
    # ========== STAGE 1: FOUNDATION MATERIALS (65% REDUCTION) ==========
    foundation = {
        'cement_bags': round((square_feet * 0.175 * floors) * quality, 2),
        'sand_cuft': round((square_feet * 0.525 * floors) * quality, 2),
        'aggregate_cuft': round((square_feet * 0.70 * floors) * quality, 2),
        'steel_kg': round((square_feet * 3.5 * floors) * quality, 2),
        'concrete_blocks': int((square_feet * 2.8) * quality),
        'water_liters': round(square_feet * 18 * floors, 2),
        'waterproofing_kg': round(square_feet * 0.175, 2)
    }
    
    # ========== STAGE 2: WALL CONSTRUCTION (60% REDUCTION) ==========
    walls = {
        'bricks': int((square_feet * 20 * floors) * quality),
        'cement_bags': round((square_feet * 0.12 * floors) * quality, 2),
        'sand_cuft': round((square_feet * 0.32 * floors) * quality, 2),
        'aac_blocks': int((square_feet * 6) * quality) if budget_range != 'low' else 0,
        'steel_mesh_kg': round((square_feet * 0.8 * floors) * quality, 2)
    }
    
    # ========== STAGE 3: FLOORING & SLAB (62% REDUCTION) ==========
    flooring = {
        'cement_bags': round((square_feet * 0.152 * floors) * quality, 2),
        'sand_cuft': round((square_feet * 0.38 * floors) * quality, 2),
        'steel_kg': round((square_feet * 3.04 * floors) * quality, 2),
        'aggregate_cuft': round((square_feet * 0.57 * floors) * quality, 2),
        'tiles_sqft': round(square_feet * floors * 0.70, 2),
        'marble_sqft': round(square_feet * 0.08, 2) if budget_range == 'high' else 0,
        'shuttering_sqft': round(square_feet * floors * 0.48, 2)
    }
    
    # ========== STAGE 4: ROOF CONSTRUCTION (63% REDUCTION) ==========
    roofing = {
        'steel_kg': round((square_feet * 4.44) * quality, 2),
        'cement_bags': round((square_feet * 0.222) * quality, 2),
        'sand_cuft': round((square_feet * 0.444) * quality, 2),
        'aggregate_cuft': round((square_feet * 0.666) * quality, 2),
        'waterproofing_kg': round(square_feet * 0.296, 2),
        'roofing_sheets_sqft': round(square_feet * 0.407, 2),
        'clay_tiles': int(square_feet * 4.2) if budget_range == 'high' else 0
    }
    
    # ========== STAGE 5: PLUMBING (55% REDUCTION) ==========
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
    
    # ========== STAGE 6: ELECTRICAL (50% REDUCTION) ==========
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
    
    # ========== STAGE 7: FINISHING (58% REDUCTION) ==========
    finishing = {
        'putty_kg': round((square_feet * 2) * 0.21, 2),
        'primer_liters': round((square_feet * 2) * 0.063, 2),
        'paint_liters': round((square_feet * 2) * 0.084, 2),
        'wall_tiles_sqft': round((bathrooms * 42) + 34, 2),
        'floor_tiles_sqft': round(square_feet * floors * 0.462, 2),
        'doors': rooms + bathrooms + 1,
        'windows': rooms * 2 + bathrooms
    }
    
    # ========== STAGE 8: CARPENTRY & INTERIOR (60% REDUCTION) ==========
    carpentry = {
        'plywood_sheets': round(rooms * 3.2 * quality, 2),
        'laminate_sqft': round(rooms * 20 * quality, 2),
        'mdf_sheets': round(rooms * 1.6 * quality, 2),
        'modular_kitchen_ft': 10 if rooms >= 3 else 6,
        'wardrobes': max(1, rooms - 2),
        'hinges': (rooms * 6) + (bathrooms * 3),
        'handles': (rooms * 4) + (bathrooms * 2)
    }
    
    # ========== STAGE 9: EXTERIOR & LANDSCAPING (65% REDUCTION) ==========
    exterior = {
        'paving_blocks_sqft': round(square_feet * 0.105, 2),
        'garden_soil_cuft': round(square_feet * 0.07, 2),
        'boundary_wall_ft': round((square_feet ** 0.5) * 1.4, 2),
        'gate': 1,
        'grills_kg': round(floors * 17.5, 2)
    }
    
    # ========== STAGE 10: MISCELLANEOUS (60% REDUCTION) ==========
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
    
    # ========== HIGHLY OPTIMIZED COST CALCULATION (45% REDUCTION) ==========
    
    # Significantly reduced material prices per sqft for each stage
    stage_prices = {
        'low': {
            'foundation': 110, 'walls': 90, 'flooring': 135,
            'roofing': 158, 'plumbing': 81, 'electrical': 68,
            'finishing': 99, 'carpentry': 180, 'exterior': 68,
            'miscellaneous': 45
        },
        'medium': {
            'foundation': 160, 'walls': 126, 'flooring': 203,
            'roofing': 228, 'plumbing': 126, 'electrical': 113,
            'finishing': 158, 'carpentry': 293, 'exterior': 113,
            'miscellaneous': 68
        },
        'high': {
            'foundation': 230, 'walls': 184, 'flooring': 293,
            'roofing': 323, 'plumbing': 193, 'electrical': 184,
            'finishing': 253, 'carpentry': 428, 'exterior': 184,
            'miscellaneous': 113
        }
    }
    
    # Calculate costs for all budget types
    all_costs = {}
    
    for budget_type in ['low', 'medium', 'high']:
        stage_costs = {}
        total_material_cost = 0
        
        # Calculate cost per stage
        for stage_name in all_materials.keys():
            # Cost per stage based on square feet with heavily reduced rates
            stage_cost = square_feet * floors * stage_prices[budget_type][stage_name]
            stage_costs[stage_name] = round(stage_cost, 2)
            total_material_cost += stage_cost
        
        # Highly reduced labor cost (18% of material cost, down from 35%)
        labor_cost = total_material_cost * 0.18
        
        # Minimal other costs (2.5% - permits, inspections, down from 5%)
        other_costs = total_material_cost * 0.025
        
        total_cost = total_material_cost + labor_cost + other_costs
        
        all_costs[budget_type] = {
            'material_cost': round(total_material_cost, 2),
            'labor_cost': round(labor_cost, 2),
            'other_costs': round(other_costs, 2),
            'total_cost': round(total_cost, 2),
            'stage_breakdown': stage_costs
        }
    
    # Highly optimized timeline estimation (35% faster)
    timeline = {
        'foundation': round(square_feet / 160, 0),
        'walls': round(square_feet / 130, 0),
        'flooring': round(square_feet / 195, 0),
        'roofing': round(square_feet / 245, 0),
        'plumbing': round(square_feet / 325, 0),
        'electrical': round(square_feet / 325, 0),
        'finishing': round(square_feet / 163, 0),
        'carpentry': round(rooms * 1.95, 0),
        'exterior': round(square_feet / 488, 0),
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


# ========== TESTING FUNCTION ==========
def print_estimation_summary(square_feet, rooms, floors, bathrooms, budget_range):
    """Helper function to test and display estimation results"""
    estimation = calculate_materials_and_cost(square_feet, rooms, floors, bathrooms, budget_range)
    
    print("=" * 80)
    print(f"HIGHLY OPTIMIZED CONSTRUCTION ESTIMATION - {budget_range.upper()} BUDGET")
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
    
    print(f"\nEstimated Timeline: {estimation['timeline']['total_days']} days")
    print(f"Total Material Types: {estimation['total_materials_count']}")
    
    print("\n💡 AGGRESSIVE OPTIMIZATION APPLIED:")
    print("   • Material quantities reduced by 60-65%")
    print("   • Material rates reduced by 45%")
    print("   • Labor costs reduced to 18% of material cost")
    print("   • Other costs reduced to 2.5%")
    print("   • Construction timeline reduced by 35%")
    
    # Show sample materials for foundation
    print(f"\n📦 SAMPLE FOUNDATION MATERIALS:")
    foundation = estimation['materials']['foundation']
    print(f"   • Cement Bags: {foundation['cement_bags']}")
    print(f"   • Sand (cu ft): {foundation['sand_cuft']}")
    print(f"   • Steel (kg): {foundation['steel_kg']}")
    print(f"   • Concrete Blocks: {foundation['concrete_blocks']}")
    print("=" * 80)


# Test with sample data (villaaa project from screenshot)
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
    
    print(f"{'Budget Type':<15} {'Material Cost':<20} {'Labor Cost':<20} {'Total Cost':<20}")
    print("-" * 75)
    for budget in ['low', 'medium', 'high']:
        costs = estimation['costs'][budget]
        print(f"{budget.upper():<15} ₹{costs['material_cost']:>16,.2f}   ₹{costs['labor_cost']:>15,.2f}   ₹{costs['total_cost']:>15,.2f}")
    print("-" * 75)