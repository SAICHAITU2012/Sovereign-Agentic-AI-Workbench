
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
import time
primes = [n for n in range(2, 20000) if all(n % p for p in range(2, int(n**0.5)+1))]
print('primes found:', len(primes))
steps = {'inputs': {'a': 42, 'b': 58}, 'formula': 'a + b', 'result': 42 + 58}
print(steps)
