def calculate_thermal_efficiency(feedwater_temp, steam_output, fuel_consumption, gcv):
    # Calculate heat input from fuel
    heat_input = fuel_consumption * gcv

    # Calculate thermal efficiency
    thermal_efficiency = (steam_output / feedwater_temp) * 100

    return thermal_efficiency