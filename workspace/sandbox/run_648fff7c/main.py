
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
cout << "Hello World" << endl;