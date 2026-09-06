
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
import re
# Key findings from inspection report
key_findings = ['Shell circum.1: 8.2mm - 8.8mm UNACCEPTABLE', 'Shell circum.2: 9.1mm - 8.8mm Acceptable']

# SOPs found in knowledge base
sops_found = ['[EMP-SOP-014_equipment_inspection_SOP.txt] approval note is filed with the inspection dossier and a copy is sent to the Mechanical Records Office.', '[EMP-SOP-014_equipment_inspection_SOP.txt]  approval note is filed with the inspection dossier and a copy is sent to the Mechanical Records Office. ', '[EMP-SOP-014_equipment_inspection_SOP.txt] The signed approval note is filed with the inspection dossier and a copy is sent to the Mechanical Records Office.']

# Compare key findings against SOPs
for s in sops_found:
    if re.search(key_findings[0], s):
        print(f'Key finding matches {s}.')
    elif re.search(key_findings[1], s):
        print(f'Key finding matches {s}.')
