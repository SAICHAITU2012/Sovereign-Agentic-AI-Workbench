
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
    # Calculate heat input from fuel
    heat_input = fuel_consumption * gcv
    # Calculate thermal efficiency
    thermal_efficiency = (heat_input / (feedwater_temp + 273.15)) * 100
    return thermal_efficiency