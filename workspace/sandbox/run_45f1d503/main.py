
import sys, types
# Air-gapped sandbox: no network, no subprocesses, no file writes outside
# the sandbox working directory are permitted from generated code.
import socket
class _BlockedSocket(socket.socket):
    def connect(self, address):
        raise ConnectionError("Sandbox: network access is disabled")
socket.socket = _BlockedSocket
import os
os.chdir(os.environ.get("SANDBOX_CWD", "."))
os.environ["HOME"] = os.environ.get("SANDBOX_CWD", ".")

# --- generated code ---
# Define given values
feedwater_temp = 105  # C
steam_output = 42  # T/hr at 65 bar
fuel_consumption = 3.1  # T/hr
gcv = 10200  # kcal/kg

# Calculate steam temperature (T_s) using the steam table or formula
# For simplicity, let's assume a steam temperature of 60 C for this example
steam_temp = 60  # C

# Calculate heat input to the boiler (Q_in)
heat_input = fuel_consumption * gcv

# Calculate thermal efficiency (η) using the formula: η = Q_out / Q_in
thermal_efficiency = steam_output / heat_input

# Print intermediate calculations and final result
print(f"Feedwater temperature: {feedwater_temp} C")
print(f"Steam output: {steam_output} T/hr at 65 bar")
print(f"Fuel consumption: {fuel_consumption} T/hr")
print(f"GCV: {gcv} kcal/kg")
print(f"Steam temperature: {steam_temp} C")
print(f"Heat input to the boiler: {heat_input} kcal")
print(f"Thermal efficiency: {thermal_efficiency:.2f}%")