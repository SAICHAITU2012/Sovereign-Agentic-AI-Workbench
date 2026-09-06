
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
key_findings = ['MANGALORE REFINERY AND PETROCHEMICALS LIMITED', 'Crude Distillation Unit - Overhead Condenser E-101', 'CDU Section, Refinery Block B', 'Inspection Date: 14 August 2026', 'Inspector _: R. Shetty, Senior Inspection Engineer']

# SOPs found in EMP-SOP-014_equipment_inspection_SOP.txt
with open('EMP-SOP-014_equipment_inspection_SOP.txt', 'r') as file:
    sop_content = file.read()

# Check for key findings in the SOPs
key_findings_in_sop = re.findall(r'(?:' + '|'.join(key_findings) + r')', sop_content)

if key_findings_in_sop:
    print('Key findings are present in the SOPs.')
else:
    print('Key findings are not present in the SOPs.')