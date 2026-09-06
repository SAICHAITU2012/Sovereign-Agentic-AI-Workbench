
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
# Constants
feedwater_temp = 105  # C
steam_output = 42  # T/hr at 65 bar
fuel_consumption = 3.1  # T/hr
gcv = 10200  # kcal/kg

# Calculate the heat input from fuel consumption
heat_input = fuel_consumption * gcv

# Calculate the heat output from steam
steam_heat_output = steam_output * 65 * 10**3  # Convert bar to Pa and convert T/hr to J/s

# Calculate the thermal efficiency
thermal_efficiency = (steam_heat_output / heat_input) * 100

# Print intermediate calculations
print(f"Feedwater temperature: {feedwater_temp} C")
print(f"Steam output: {steam_output} T/hr at 65 bar")
print(f"Heat input from fuel consumption: {heat_input} kcal/kg")
print(f"Heat output from steam: {steam_heat_output} J/s")
print(f"Thermal efficiency: {thermal_efficiency:.2f}%")

# Print final result
print(f"The overall thermal efficiency of the boiler is {thermal_efficiency:.2f}%.")