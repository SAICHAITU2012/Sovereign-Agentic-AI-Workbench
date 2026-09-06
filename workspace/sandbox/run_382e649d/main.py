
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
# Define the minimum age required to vote
MIN_AGE = 18

# Prompt the user for their age
age = int(input("Please enter your age: "))

# Perform intermediate calculations (if needed)
# For example, you might calculate the number of years left until voting eligibility

# Print intermediate calculation steps if needed
print(f"Age entered: {age}")

# Determine eligibility based on the minimum age requirement
if age >= MIN_AGE:
    print("You are eligible to vote.")
else:
    print(f"You are not eligible to vote. You need at least {MIN_AGE} years to vote.")