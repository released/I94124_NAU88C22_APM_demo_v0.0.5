"""Check complete Keil build inputs, including reviewed binary dependencies."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

TARGETS = {'Colsonic_16k_USB_UAC': 'Colsonic_apm',
           'Colsonic_16k_I2S_I2C': 'Colsonic_16k'}
BINARY_HASHES = {
    'SampleCode/Template/' + target + '/Colsonic/' + name: digest
    for target in TARGETS for name, digest in (
        ('colsonic_apm_v0.0.5_20260213_0_0.lib',
         '4505a89e1d13d924057dcd8c660337c7ac8bae8dd9f07bcdd10057308dc9342e'),
        ('colsonicdata.bin',
         'ec533a82819a0940c44b879bd0a16485a5d4699065f9781f192600dad2b62af6'))}
BINARY_HASHES['SampleCode/Template/Colsonic_16k_USB_UAC/Library/CMSIS/Lib/ARM/arm_cortexM4lf_math.lib'] = (
    'ab4662066914c19ae1aa24c30309da19c108bef334d9d2ffbe04a5954e65d321')
KEIL_OPTIONS = {'SampleCode/Template/' + target + '/KEIL/' + name + '.uvoptx'
                for target, name in TARGETS.items()}


def validate(root, available=None):
    root = root.resolve()
    required = set()

    def require(file):
        file = file.resolve()
        if not file.is_relative_to(root):
            raise ValueError('Build input escapes project root: ' + str(file))
        name = file.relative_to(root).as_posix()
        if not file.is_file() or (available is not None and name not in available):
            raise ValueError('Build input missing from delivery: ' + name)
        required.add(name)
        return file

    for name, expected in BINARY_HASHES.items():
        file = require(root / name)
        if hashlib.sha256(file.read_bytes()).hexdigest() != expected:
            raise ValueError('Build dependency hash mismatch: ' + name)
    for name in KEIL_OPTIONS:
        require(root / name)
    references = 0
    for folder, project_name in TARGETS.items():
        keil = root / 'SampleCode/Template' / folder / 'KEIL'
        project = require(keil / (project_name + '.uvprojx'))
        tree = ET.parse(project)
        common = tree.find('.//TargetCommonOption')
        if (common.findtext('Device') != 'I94124'
                or common.findtext('PackID') != 'Nuvoton.NuVoice_ISD_DFP.1.0.20'
                or common.findtext('SFDFile') != r'$$Device:I94124$SVD\Nuvoton\I94100_v1_3.svd'):
            raise ValueError('Unexpected device pack or nonportable SVD setting: ' + folder)
        for node in tree.findall('.//FilePath'):
            file = require(keil / node.text.replace('\\', '/'))
            references += 1
            if file.suffix.lower() in {'.s', '.inc'}:
                for value in re.findall(r'^\s*INCBIN\s+([^;\r\n]+)',
                                        file.read_text(encoding='ascii'), re.M | re.I):
                    require(keil / value.strip().strip('"').replace('\\', '/'))
        linker = tree.find('.//LDads')
        if linker is not None and linker.findtext('useFile') == '1':
            require(keil / linker.findtext('ScatterFile').replace('\\', '/'))
        for node in tree.findall('.//IncludePath'):
            for value in filter(None, (node.text or '').split(';')):
                directory = (keil / value.replace('\\', '/')).resolve()
                if not directory.is_relative_to(root) or not directory.is_dir():
                    raise ValueError('Missing/external include directory: ' + value)
                prefix = directory.relative_to(root).as_posix() + '/'
                if available is not None and not any(p.startswith(prefix) for p in available):
                    raise ValueError('Include directory absent from delivery: ' + prefix)
    return {'targets': len(TARGETS), 'project_file_references': references,
            'reviewed_binaries': len(BINARY_HASHES), 'shared_keil_options': len(KEIL_OPTIONS),
            'required_inputs': len(required), 'result': 'PASS'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--publication', action='store_true',
                        help='Check the Git candidate scope, including ignore rules.')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    available = None
    if args.publication:
        top = subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], cwd=root).decode().strip()
        if Path(top).resolve() != root:
            raise ValueError('Unexpected Git root')
        available = set(subprocess.check_output([
            'git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'],
            cwd=root).decode('utf-8').split('\0'))
    print(json.dumps(validate(root, available)))


if __name__ == '__main__':
    main()
