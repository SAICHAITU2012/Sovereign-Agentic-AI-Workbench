# Constants
feedwater_temp = 105  # C
steam_output = 42  # T/hr at 65 bar
fuel_consumption = 3.1  # T/hr
gcv = 10200  # kcal/kg

# Calculate steam temperature (T_s)
T_s = (feedwater_temp * 9/5 + 32) + 105  # C to K

# Calculate steam pressure (P_s)
P_s = 65 * 10**5  # bar to Pa

# Calculate heat input (Q_in)
Q_in = fuel_consumption * gcv  # kcal/hr

# Calculate heat output (Q_out)
Q_out = steam_output * P_s / 1000  # T/hr to kW

# Calculate thermal efficiency (η)
η = Q_out / Q_in * 100  # %

print(f"Feedwater temperature: {feedwater_temp} C")
print(f"Steam output: {steam_output} T/hr at 65 bar")
print(f"Fuel consumption: {fuel_consumption} T/hr")
print(f"GCV: {gcv} kcal/kg")

print(f"Steam temperature (T_s): {T_s:.2f} K")
print(f"Steam pressure (P_s): {P_s:.2f} Pa")

print(f"Heat input (Q_in): {Q_in:.2f} kcal/hr")
print(f"Heat output (Q_out): {Q_out:.2f} kW")

print(f"Thermal efficiency (η): {η:.2f}%")