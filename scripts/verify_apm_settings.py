"""Verify ordinary USB/I2C source, linked stack and actual NS call arguments."""
from pathlib import Path
import argparse
import json
import re
import struct
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
FROMELF = Path(r'C:\Keil_v5\ARM\ARMCLANG\bin\fromelf.exe')
NS_BITS = struct.unpack('<I', struct.pack('<f', 0.85))[0]
STACK_BYTES = 4096


def ns_arguments(disassembly, binary, functions, expected_bits=NS_BITS):
    results = []
    for name in functions:
        match = re.search(r'^    ' + re.escape(name) + r'\n(.*?)(?=^    [A-Za-z_$]|\Z)',
                          disassembly, re.M | re.S)
        if not match:
            raise AssertionError('Missing linked function: ' + name)
        body = match[1]
        calls = list(re.finditer(r'\b(?:BL|B\.W|B)\s+Colsonic_ns_set\b', body))
        if len(calls) != 1:
            raise AssertionError(name + ': expected one NS call')
        # Arm Compiler 6 emits a PC-relative float literal for 0.85f.
        loads = list(re.finditer(r'\bVLDR\s+s0,\[pc,#[^\]]+\]\s*;\s*'
                                 r'\[0x([0-9a-fA-F]+)\]\s*=\s*0x([0-9a-fA-F]+)',
                                 body[:calls[0].start()]))
        if not loads:
            raise AssertionError(name + ': NS float argument load not found')
        load = loads[-1]
        address, value = int(load[1], 16), int(load[2], 16)
        if value != expected_bits or struct.unpack_from('<I', binary, address)[0] != value:
            raise AssertionError(name + ': NS argument differs from the requested preset')
        results.append({'function': name, 'ns_bits': hex(value), 'literal_address': hex(address)})
    return results


def verify(folder, functions):
    source = ROOT / 'SampleCode/Template' / folder
    keil = source / 'KEIL'
    project = next(keil.glob('*.uvprojx'))
    target = ET.parse(project).getroot().find('Targets/Target')
    paths = [f.findtext('FilePath') for f in target.findall('Groups/Group/Files/File')]
    if any('diag' in path.lower() for path in paths):
        raise AssertionError('Diagnostic source in ordinary project')
    text = (source / 'Util/misc.c').read_text(encoding='ascii')
    values = re.findall(r'Colsonic_ns_set\(([^)]+)\)', text)
    if values != ['0.85f'] * len(functions):
        raise AssertionError(folder + ': boot/reset NS presets differ')
    startup = (keil / 'startup_I94100.s').read_text(encoding='ascii')
    if int(re.search(r'Stack_Size\s+EQU\s+(0x[0-9a-fA-F]+)', startup)[1], 16) != STACK_BYTES:
        raise AssertionError('Startup stack is not 4 KiB')
    output = target.findtext('TargetOption/TargetCommonOption/OutputName')
    mapping = (keil / 'lst' / (output + '.map')).read_text(errors='replace')
    stack = re.search(r'^\s*Stack_Mem\s+0x([0-9a-fA-F]+)\s+Data\s+(\d+)\s+.*\(STACK\)', mapping, re.M)
    top = re.search(r'^\s*__initial_sp\s+0x([0-9a-fA-F]+)', mapping, re.M)
    if not stack or not top or int(stack[2]) != STACK_BYTES or int(top[1], 16)-int(stack[1], 16) != STACK_BYTES:
        raise AssertionError('Linked stack allocation is not 4 KiB')
    if 'AudioDiag_' in mapping or 'g_audioDiag' in mapping:
        raise AssertionError('Diagnostic symbols linked into ordinary firmware')
    binary = (keil / 'obj' / (output + '.bin')).read_bytes()
    disassembly = subprocess.check_output([str(FROMELF), '--text', '-c',
        str(keil / 'obj' / (output + '.axf'))], text=True, errors='replace')
    calls = ns_arguments(disassembly, binary, functions)
    result = {'target': output, 'ns': 0.85, 'stack_bytes': STACK_BYTES,
              'ns_calls': calls, 'diagnostic_symbols': False, 'result': 'PASS'}
    print(json.dumps(result))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-Target', choices=['All', 'USB', 'I2C'], default='All')
    args = parser.parse_args()
    if args.Target in ['All', 'USB']:
        verify('Colsonic_16k_USB_UAC', ['Colsonic_Init'])
    if args.Target in ['All', 'I2C']:
        verify('Colsonic_16k_I2S_I2C', ['Colsonic_Init', 'Stop_Audio'])
