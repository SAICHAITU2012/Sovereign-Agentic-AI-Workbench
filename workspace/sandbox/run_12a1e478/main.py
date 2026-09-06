
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
def add_numbers(a, b):
    # Print initial addition step
    print(f"Adding {a} and {b}")
    
    # Perform addition
    result = a + b
    
    # Print intermediate calculation step
    print(f"{a} + {b} equals {result}")
    
    # Print final result line
    print(f"The sum of {a} and {b} is {result}")

# Example usage:
add_numbers(5, 3)