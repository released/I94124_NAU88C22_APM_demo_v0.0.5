"""Verify/build only the prospective Git delivery in a fresh owned copy."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', action='store_true', help='Rebuild both ordinary firmware targets.')
    parser.add_argument('--uv4', default=r'C:\Keil_v5\UV4\UV4.exe')
    args = parser.parse_args()
    pub = load('publisher', ROOT / 'scripts/github_push.py')
    fixture = load('fixture_retirement', ROOT / 'tests/test_github_push.py')
    files = pub.snapshot(ROOT)
    delivery = pub.check_build_delivery(ROOT, files)
    run = ROOT / ('.verify_' + uuid.uuid4().hex[:8])
    work = run / 'w'
    work.mkdir(parents=True, exist_ok=False)
    evidence = ROOT / '.local/checkout_verification.json'
    evidence.parent.mkdir(exist_ok=True)
    receipt = {'producer': 'tests/verify_checkout.py', 'byte_limit': 100000000,
               'central_exception': 'Source project outside configured central project_roots; '
               'short project-local run avoids legacy compiler path limits.',
               'source_files': len(files), 'delivery': delivery,
               'build_requested': args.build, 'build_exit': None,
               'copy_verified': False, 'removed': False, 'work': str(work),
               'source_sha256': hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()}
    status = 0
    try:
        for name, digest in files.items():
            source, destination = ROOT / name, work / name
            if os.name == 'nt' and len(str(destination)) >= 260:
                raise ValueError('Checkout fixture exceeds compiler path limit: ' + name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            if hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
                raise ValueError('Checkout copy differs: ' + name)
        pub.check_build_delivery(work)
        receipt['copy_verified'] = True
        if args.build:
            # Invocation-local temporary files stay in this owned run.
            temp = work / 'temporary'
            temp.mkdir()
            environment = dict(os.environ, TEMP=str(temp), TMP=str(temp))
            result = subprocess.run([
                'powershell', '-NoProfile', '-File', str(work / 'BUILD.ps1'),
                '-Target', 'All', '-UV4', args.uv4], cwd=work, env=environment,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            receipt['build_exit'] = result.returncode
            receipt['build_output_tail'] = result.stdout.decode('utf-8', 'replace').splitlines()[-18:]
            status = result.returncode
        receipt['targets'] = {}
        for folder, project in pub.TARGETS.items():
            keil = work / 'SampleCode/Template' / folder / 'KEIL'
            log = keil / 'build.log'
            info = {'build_log_present': log.is_file()}
            if log.is_file():
                lines = log.read_text(encoding='utf-8', errors='replace').splitlines()
                info['summary'] = [line for line in lines if any(x in line for x in
                                   ('Error(s)', 'Warning(s)', 'Program Size:', 'error:', 'Error:'))][-8:]
            info['images'] = {file.name: {'bytes': file.stat().st_size,
                                          'sha256': hashlib.sha256(file.read_bytes()).hexdigest()}
                              for file in (keil / 'obj').glob('*')
                              if file.suffix.lower() in {'.bin', '.hex', '.axf'}}
            for name, image in info['images'].items():
                reference = ROOT / 'SampleCode/Template' / folder / 'KEIL/obj' / name
                if name.endswith('.bin') and reference.is_file():
                    previous = reference.read_bytes()
                    current = (keil / 'obj' / name).read_bytes()
                    def normalize_time(data):
                        data = re.sub(rb'\d{2}:\d{2}:\d{2}', b'00:00:00', data)
                        return re.sub(rb'[A-Z][a-z]{2} [ 0-3]\d \d{4}', b'Jan 01 2000', data)
                    image['reference_sha256'] = hashlib.sha256(previous).hexdigest()
                    image['same_except_build_time'] = normalize_time(previous) == normalize_time(current)
                    image['changed_bytes'] = sum(a != b for a, b in zip(previous, current)) + abs(len(previous)-len(current))
            receipt['targets'][folder] = info
    except Exception as error:
        status = 1
        receipt['error'] = str(error)
    finally:
        # The copy and compiler are the only producers in this exclusively owned run.
        disk_work = Path('\\\\?\\' + str(work)) if os.name == 'nt' else work
        entries = list(disk_work.rglob('*'))
        for file in entries:
            if file.is_symlink() or getattr(file.lstat(), 'st_file_attributes', 0) & 0x400:
                raise RuntimeError('Reparse fixture preserved for review: ' + str(file))
        generated = [file for file in entries if file.is_file()]
        manifest = {str(file.relative_to(disk_work)): hashlib.sha256(file.read_bytes()).hexdigest()
                    for file in generated}
        receipt.update(generated_files=len(generated), generated_bytes=sum(file.stat().st_size for file in generated),
                       retirement_manifest_sha256=hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest())
        evidence.write_text(json.dumps(receipt, indent=2), encoding='utf-8')
        fixture.retire(work, manifest)
        receipt['removed'] = not work.exists()
        evidence.write_text(json.dumps(receipt, indent=2), encoding='utf-8')
        run.rmdir()
    print(json.dumps({key: receipt[key] for key in
                      ('delivery', 'source_files', 'copy_verified', 'build_exit', 'removed')}))
    if receipt.get('error'):
        print(receipt['error'], file=sys.stderr)
    for target, info in receipt.get('targets', {}).items():
        print(target + ': ' + ' | '.join(info.get('summary', [])))
    if status and receipt.get('build_output_tail'):
        print('\n'.join(receipt['build_output_tail']), file=sys.stderr)
    return status


if __name__ == '__main__':
    sys.exit(main())
