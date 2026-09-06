
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
def calculate_thermal_efficiency(feedwater_temp, steam_output, fuel_consumption, gcv):
    heat_input = feedwater_temp + 273.15
    fuel_consumption_rate = fuel_consumption * 0.98 # Convert to kg/hr
    fuel_mass = fuel_consumption_rate * gcv / 4.1868 # Convert GCV to MJ/kg
    efficiency = (heat_input / fuel_mass) * 100
    return efficiency