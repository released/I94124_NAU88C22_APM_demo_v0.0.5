"""Reviewed source publication; no repository creation, build or force push."""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path


class PublicationError(RuntimeError):
    pass


def run(root, *args, data=None, ok=(0,)):
    if args[0] == 'git':
        args = ('git', '-c', 'core.longpaths=true', *args[1:])
    result = subprocess.run(args, cwd=root, input=data, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    if result.returncode not in ok:
        raise PublicationError(result.stderr.decode('utf-8', 'replace').strip()
                               or 'Command failed: ' + args[0])
    return result


def git(root, *args, **kwargs):
    return run(root, 'git', *args, **kwargs).stdout.decode('utf-8').strip('\r\n')


def head(root):
    result = run(root, 'git', 'rev-parse', '--verify', 'HEAD', ok=(0, 128))
    return result.stdout.decode().strip() if result.returncode == 0 else None


def paths(root, *args):
    return set(filter(None, run(root, 'git', *args, '-z').stdout.decode('utf-8').split('\0')))


def safe_path(name):
    p = name.lower()
    parts = p.split('/')
    denied = {'verification', 'test_wave', '.local', '__la', 'backup', '__pycache__',
              'diagnostics', 'node_modules', 'obj', 'lst', 'objects', 'listings'}
    if (any(x in denied for x in parts) or p.startswith('docs/internal/')
            or p in {'docs/review.md', 'docs/legacy_channels.md', 'build_audio_diag.ps1',
                     'build_stack_control.ps1'}
            or any(x in p for x in ('audio_diag', 'stack_control'))
            or Path(p).name in {'agents.md', 'claude.md', 'workspace_rules.md', 'spec.md',
                               'self_check.md', 'handoff.md', 'codex_handoff.md',
                               'manual_cleanup.md'}
            or any(x in parts for x in ('.env',))
            or Path(p).name.startswith(('.env.', 'nulink'))
            or re.search(r'\.(?:bin|lib|a|axf|elf|hex|exe|dll|o|obj|d|dep|crf|map|lnp|log|'
                         r'zip|7z|wav|jpg|xlsx|pem|key|pyc|bak|uvoptx?|averyc|sample)$', p)
            or '.uvguix' in p or any(c in name for c in '\r\n\t')
            or name.startswith('/') or '..' in parts or '\\' in name):
        raise PublicationError('Local-only or unsupported publication path: ' + name)


def safe_content(name, data):
    if len(data) >= 100 * 1024 * 1024:
        raise PublicationError('File exceeds GitHub size limit: ' + name)
    if re.search(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|'
                 rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|'
                 rb'[CD]:[\\/]Users[\\/][^\s"<>]+|D:[\\/](?:11101465|SourceCode)[\\/])',
                 data, re.I):
        raise PublicationError('Credential or personal-path candidate: ' + name)


def snapshot(root):
    result = {}
    for name in sorted(paths(root, 'ls-files', '--cached', '--others', '--exclude-standard')):
        safe_path(name)
        file = root / name
        if not file.exists():
            continue
        for item in (file, *file.parents):
            if item == root.parent:
                break
            if item.is_symlink() or getattr(item.lstat(), 'st_file_attributes', 0) & 0x400:
                raise PublicationError('Reparse/symlink path: ' + name)
        data = file.read_bytes()
        safe_content(name, data)
        result[name] = hashlib.sha256(data).hexdigest()
    return result


def firmware_digest(files):
    # Include executable firmware/build/test sources, excluding editorial/publisher files.
    selected = {p: h for p, h in files.items() if p.startswith(('Library/', 'SampleCode/'))
                or p in {'BUILD.ps1', 'VERIFY.ps1', 'tests/channel_test.c',
                         'tests/RUN_CHANNEL_TESTS.ps1', 'scripts/verify_apm_settings.py',
                         'scripts/verify_source_encoding.ps1'}}
    return hashlib.sha256(json.dumps(selected, sort_keys=True).encode()).hexdigest()


def board_gate(root, config, files):
    if config['visibility'] != 'public':
        return
    record = root / '.local/hardware_acceptance.json'
    if not record.is_file():
        raise PublicationError('Public firmware requires matching local board acceptance.')
    acceptance = json.loads(record.read_text(encoding='utf-8'))
    if (acceptance.get('board') != 'I94124/NAU88C22'
            or acceptance.get('result') != 'accepted'
            or set(acceptance.get('interfaces', [])) != {'USB', 'I2C/I2S'}
            or acceptance.get('firmware_sha256') != firmware_digest(files)):
        raise PublicationError('Firmware differs from the accepted real-board scope.')
    dependencies = acceptance.get('dependencies', {})
    expected = {'SampleCode/Template/' + target + '/Colsonic/' + name
                for target in ('Colsonic_16k_USB_UAC', 'Colsonic_16k_I2S_I2C')
                for name in ('colsonic_apm_v0.0.5_20260213_0_0.lib', 'colsonicdata.bin')}
    if set(dependencies) != expected:
        raise PublicationError('Board acceptance lacks the exact library/profile scope.')
    for name, digest in dependencies.items():
        file = root / name
        if not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest() != digest:
            raise PublicationError('Accepted library/profile is missing or changed: ' + name)


def history_guard(root):
    for line in git(root, 'rev-list', '--objects', '--all').splitlines():
        if ' ' not in line:
            continue
        oid, name = line.split(' ', 1)
        safe_path(name)
        if git(root, 'cat-file', '-t', oid) == 'blob':
            safe_content(name, run(root, 'git', 'cat-file', 'blob', oid).stdout)


class GitHubRemote:
    def validate(self, root, config):
        repo = config['repository']
        allowed = {'https://github.com/' + repo + '.git', 'https://github.com/' + repo,
                   'git@github.com:' + repo + '.git'}
        for kind in ((), ('--push',)):
            urls = git(root, 'remote', 'get-url', *kind, '--all', 'origin').splitlines()
            if len(urls) != 1 or urls[0] not in allowed:
                raise PublicationError('Origin destination mismatch.')
        meta = json.loads(run(root, 'gh', 'api', 'repos/' + repo).stdout)
        if (meta['full_name'] != repo or bool(meta['private']) != (config['visibility'] == 'private')
                or not meta.get('permissions', {}).get('push')):
            raise PublicationError('Live repository identity/visibility/permission mismatch.')


def remote_head(root, config, adapter):
    adapter.validate(root, config)
    refs = git(root, 'ls-remote', 'origin').splitlines()
    if not refs:
        return None
    branch_ref = 'refs/heads/' + config['branch']
    matches = [line.split()[0] for line in refs if line.split()[1] == branch_ref]
    if len(matches) != 1:
        raise PublicationError('Nonempty destination lacks the intended branch.')
    remote = matches[0]
    if not head(root):
        raise PublicationError('Destination is nonempty but local HEAD is unborn.')
    exists = run(root, 'git', 'cat-file', '-e', remote + '^{commit}', ok=(0, 1, 128))
    if exists.returncode or run(root, 'git', 'merge-base', '--is-ancestor', remote, 'HEAD',
                               ok=(0, 1)).returncode:
        raise PublicationError('Remote is ahead/diverged/unknown; review and integrate separately.')
    return remote


def local_plan(root, config):
    if Path(git(root, 'rev-parse', '--show-toplevel')).resolve() != root:
        raise PublicationError('Unexpected Git top-level.')
    if config['branch'] != 'main' or git(root, 'symbolic-ref', '--short', 'HEAD') != config['branch']:
        raise PublicationError('Expected the configured main branch.')
    for marker in ('MERGE_HEAD', 'CHERRY_PICK_HEAD', 'REVERT_HEAD', 'rebase-merge',
                   'rebase-apply', 'sequencer', 'index.lock'):
        if Path(git(root, 'rev-parse', '--git-path', marker)).is_absolute():
            active = Path(git(root, 'rev-parse', '--git-path', marker))
        else:
            active = root / git(root, 'rev-parse', '--git-path', marker)
        if active.exists():
            raise PublicationError('Active Git operation: ' + marker)
    if paths(root, 'diff', '--cached', '--name-only'):
        raise PublicationError('Existing staged work must be reviewed separately.')
    files = snapshot(root)
    history_guard(root)
    board_gate(root, config, files)
    changed = paths(root, 'ls-files', '--others', '--exclude-standard')
    if head(root):
        changed |= paths(root, 'diff', '--name-only', '--no-renames', 'HEAD')
    for name in changed:
        safe_path(name)
    return {'head': head(root), 'files': files, 'changed': sorted(changed)}


def verify_tree(root, revision, expected):
    actual = {}
    for entry in run(root, 'git', 'ls-tree', '-r', '-z', revision).stdout.split(b'\0'):
        if not entry:
            continue
        meta, raw_name = entry.split(b'\t', 1)
        mode, kind, oid = meta.decode().split()
        name = raw_name.decode('utf-8')
        safe_path(name)
        if mode not in ('100644', '100755') or kind != 'blob':
            raise PublicationError('Unsupported tree entry: ' + name)
        data = run(root, 'git', 'cat-file', 'blob', oid).stdout
        safe_content(name, data)
        actual[name] = hashlib.sha256(data).hexdigest()
    if actual != expected:
        raise PublicationError('Actual staged/committed content differs from reviewed content.')


def publish(root, config, check_only=False, message='Update NAU88C22 APM demo',
            confirm=input, adapter=None):
    adapter = adapter or GitHubRemote()
    plan = local_plan(root, config)
    print('Destination: ' + config['repository'] + ' (' + config['visibility'] + ')')
    for name in plan['changed']:
        print(('DELETE ' if name not in plan['files'] else 'UPDATE ') + name)
    review_hash = hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()
    print('Reviewed files: %d; changes: %d; SHA256: %s' %
          (len(plan['files']), len(plan['changed']), review_hash))
    if 'origin' not in git(root, 'remote').splitlines():
        if check_only:
            print('LOCAL PREVIEW OK; origin is not configured. No staging/commit/push.')
            return
        raise PublicationError('Create/confirm the repository and origin separately first.')
    remote = remote_head(root, config, adapter)
    if check_only:
        print('PREVIEW OK; no staging/commit/push.')
        return
    if not plan['changed'] and remote == plan['head']:
        print('No changes; already synchronized.')
        return
    answer = confirm('Type ' + config['repository'] + ' to commit/push; anything else cancels: ')
    if answer != config['repository']:
        print('Cancelled; no staging/commit/push.')
        return
    if local_plan(root, config) != plan or remote_head(root, config, adapter) != remote:
        raise PublicationError('Local/remote state changed after review; preview again.')
    if plan['changed']:
        specs = ('\0'.join(plan['changed']) + '\0').encode('utf-8')
        run(root, 'git', '--literal-pathspecs', 'add', '-A', '--pathspec-from-file=-',
            '--pathspec-file-nul', data=specs)
        verify_tree(root, git(root, 'write-tree'), plan['files'])
        if run(root, 'git', 'diff', '--cached', '--quiet', ok=(0, 1)).returncode:
            run(root, 'git', 'commit', '-m', message)
    verify_tree(root, 'HEAD', plan['files'])
    board_gate(root, config, plan['files'])
    if remote_head(root, config, adapter) != remote:
        raise PublicationError('Remote changed; local commit retained, push withheld.')
    run(root, 'git', 'push', '-u', 'origin', 'HEAD:refs/heads/' + config['branch'])
    if remote_head(root, config, adapter) != head(root):
        raise PublicationError('Push SHA verification failed; inspect the remote.')
    print('Push verified: ' + head(root))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only', action='store_true')
    parser.add_argument('--message', default='Update NAU88C22 APM demo')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / 'github_repository.json').read_text(encoding='utf-8'))
    if (not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', config['repository'])
            or config['visibility'] not in ('public', 'private')):
        raise PublicationError('Invalid repository configuration.')
    publish(root, config, args.check_only, args.message)


if __name__ == '__main__':
    try:
        main()
    except (PublicationError, OSError, ValueError, KeyError, EOFError) as error:
        print('STOP: ' + str(error), file=sys.stderr)
        sys.exit(1)
