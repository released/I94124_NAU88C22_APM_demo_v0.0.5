"""Offline publisher fixtures. Uses only fresh, owned local Git repositories."""
import contextlib
import argparse
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import unittest
import uuid
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('publisher', ROOT / 'scripts/github_push.py')
pub = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pub)
WORK = None


def require_fixture_root(root):
    if (not root.is_relative_to(WORK)
            or Path(pub.git(root, 'rev-parse', '--show-toplevel')).resolve() != root):
        raise pub.PublicationError('Fixture Git discovery escaped its dedicated repository')


class LocalRemote:
    def __init__(self, expected):
        self.expected = str(expected)

    def validate(self, root, config):
        if pub.git(root, 'remote', 'get-url', 'origin') != self.expected:
            raise pub.PublicationError('Fixture destination mismatch')


class PublisherTests(unittest.TestCase):
    def setUp(self):
        self.case = WORK / ('c%02d' % len(list(WORK.iterdir())))
        self.case.mkdir()
        self.root = self.case / 's p'
        self.remote = self.case / 'r.git'
        pub.run(self.case, 'git', 'init', '--bare', str(self.remote))
        pub.run(self.case, 'git', 'init', '-b', 'main', str(self.root))
        require_fixture_root(self.root)
        pub.git(self.root, 'config', 'user.name', 'Fixture')
        pub.git(self.root, 'config', 'user.email', 'fixture@example.invalid')
        pub.git(self.root, 'config', 'commit.gpgsign', 'false')
        pub.git(self.root, 'remote', 'add', 'origin', str(self.remote))
        (self.root / '.gitignore').write_text('.local/\n*.wav\nverification/\n')
        (self.root / '.gitattributes').write_text('* -text\n')
        (self.root / 'README.md').write_text('Example\n')
        self.config = {'repository': 'fixture/example', 'visibility': 'private', 'branch': 'main'}
        self.adapter = LocalRemote(self.remote)

    def publish(self, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            pub.publish(self.root, self.config, adapter=self.adapter,
                        confirm=kwargs.pop('confirm', lambda _: 'fixture/example'), **kwargs)

    def test_empty_repeat_and_no_change(self):
        self.publish(check_only=True)
        self.assertIsNone(pub.head(self.root))
        self.publish()
        first = pub.head(self.root)
        self.publish()
        self.assertEqual(first, pub.head(self.root))
        (self.root / 'README.md').write_text('Updated\n')
        self.publish()
        self.assertNotEqual(first, pub.head(self.root))
        self.assertIn(pub.head(self.root), pub.git(self.root, 'ls-remote', 'origin'))

    def test_cancel_and_preserve_index(self):
        self.publish(confirm=lambda _: '')
        self.assertIsNone(pub.head(self.root))
        self.assertFalse(pub.paths(self.root, 'diff', '--cached', '--name-only'))

    def test_fixture_top_level_guard(self):
        child = self.root / 'child'
        child.mkdir()
        before = (self.root / '.git/config').read_bytes()
        with self.assertRaises(pub.PublicationError):
            require_fixture_root(child)
        self.assertEqual(before, (self.root / '.git/config').read_bytes())

    def test_untracked_exclusions_and_tracked_private(self):
        (self.root / '.local').mkdir()
        (self.root / '.local/private.txt').write_text('local')
        (self.root / 'recording.wav').write_bytes(b'fixture')
        self.publish()
        self.assertNotIn('private.txt', pub.git(self.root, 'ls-tree', '-r', '--name-only', 'HEAD'))
        pub.git(self.root, 'add', '-f', '.local/private.txt')
        pub.git(self.root, 'commit', '-m', 'Private fixture')
        with self.assertRaises(pub.PublicationError):
            self.publish()

    def test_private_in_history(self):
        self.publish()
        (self.root / '.local').mkdir()
        (self.root / '.local/private.txt').write_text('local')
        pub.git(self.root, 'add', '-f', '.local/private.txt')
        pub.git(self.root, 'commit', '-m', 'Private fixture')
        pub.git(self.root, 'rm', '.local/private.txt')
        pub.git(self.root, 'commit', '-m', 'Remove fixture')
        with self.assertRaises(pub.PublicationError):
            self.publish()

    def test_wrong_remote(self):
        pub.git(self.root, 'remote', 'set-url', 'origin', str(self.case / 'wrong.git'))
        with self.assertRaises(pub.PublicationError):
            self.publish()
        self.assertIsNone(pub.head(self.root))

    def test_ahead_and_diverged(self):
        self.publish()
        other = self.case / 'other'
        pub.run(self.case, 'git', 'clone', '-b', 'main', str(self.remote), str(other))
        require_fixture_root(other)
        pub.git(other, 'config', 'user.name', 'Fixture')
        pub.git(other, 'config', 'user.email', 'fixture@example.invalid')
        pub.git(other, 'config', 'commit.gpgsign', 'false')
        (other / 'remote.txt').write_text('Remote change')
        pub.git(other, 'add', 'remote.txt')
        pub.git(other, 'commit', '-m', 'Remote advance')
        pub.git(other, 'push', 'origin', 'main')
        with self.assertRaises(pub.PublicationError):
            self.publish()
        pub.git(self.root, 'fetch', 'origin')
        (self.root / 'local.txt').write_text('Local change')
        pub.git(self.root, 'add', 'local.txt')
        pub.git(self.root, 'commit', '-m', 'Local divergence')
        with self.assertRaises(pub.PublicationError):
            self.publish()

    def test_staged_work(self):
        pub.git(self.root, 'add', 'README.md')
        before = pub.git(self.root, 'write-tree')
        with self.assertRaises(pub.PublicationError):
            self.publish()
        self.assertEqual(before, pub.git(self.root, 'write-tree'))

    def test_changed_after_confirmation(self):
        def change(_):
            (self.root / 'README.md').write_text('Changed during review')
            return 'fixture/example'
        with self.assertRaises(pub.PublicationError):
            self.publish(confirm=change)
        self.assertIsNone(pub.head(self.root))

    def test_commit_hook_injection_is_withheld(self):
        hook = self.root / '.git/hooks/pre-commit'
        hook.write_text('#!/bin/sh\nmkdir -p .local\nprintf secret > .local/leak.txt\n'
                        'git add -f .local/leak.txt\n')
        hook.chmod(0o755)
        with self.assertRaises(pub.PublicationError):
            self.publish()
        self.assertEqual('', pub.git(self.root, 'ls-remote', 'origin'))
        self.assertTrue(hook.is_file())

    def test_public_board_scope(self):
        self.config['visibility'] = 'public'
        (self.root / 'SampleCode').mkdir()
        (self.root / 'SampleCode/main.c').write_text('int main(void) { return 0; }\n')
        with self.assertRaises(pub.PublicationError):
            self.publish(check_only=True)
        (self.root / '.local').mkdir()
        record = {'board': 'I94124/NAU88C22', 'result': 'accepted',
                  'interfaces': ['USB', 'I2C/I2S'],
                  'firmware_sha256': pub.firmware_digest(pub.snapshot(self.root))}
        deps = {}
        for target in ('Colsonic_16k_USB_UAC', 'Colsonic_16k_I2S_I2C'):
            for name in ('colsonic_apm_v0.0.5_20260213_0_0.lib', 'colsonicdata.bin'):
                file = self.root / 'SampleCode/Template' / target / 'Colsonic' / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_bytes(b'synthetic dependency identity only')
                deps[file.relative_to(self.root).as_posix()] = hashlib.sha256(file.read_bytes()).hexdigest()
        with (self.root / '.gitignore').open('a') as stream:
            stream.write('*.lib\n*.bin\n')
        record['dependencies'] = deps
        (self.root / '.local/hardware_acceptance.json').write_text(json.dumps(record))
        self.publish(check_only=True)
        dependency = self.root / next(iter(deps))
        original = dependency.read_bytes()
        dependency.write_bytes(b'changed')
        with self.assertRaises(pub.PublicationError):
            self.publish(check_only=True)
        dependency.write_bytes(original)
        (self.root / 'SampleCode/main.c').write_text('int main(void) { return 1; }\n')
        with self.assertRaises(pub.PublicationError):
            self.publish(check_only=True)

    def test_live_metadata_guards(self):
        pub.git(self.root, 'remote', 'set-url', 'origin', 'https://github.com/fixture/example.git')
        original_run = pub.run
        metadata = {'full_name': 'fixture/example', 'private': True, 'permissions': {'push': True}}
        def response(root, *args, **kwargs):
            if args[0] == 'gh':
                return subprocess.CompletedProcess(args, 0, json.dumps(metadata).encode(), b'')
            return original_run(root, *args, **kwargs)
        adapter = pub.GitHubRemote()
        with mock.patch.object(pub, 'run', side_effect=response):
            adapter.validate(self.root, self.config)
            for key, value in [('full_name', 'fixture/wrong'), ('private', False),
                               ('permissions', {'push': False})]:
                previous = metadata[key]
                metadata[key] = value
                with self.assertRaises(pub.PublicationError):
                    adapter.validate(self.root, self.config)
                metadata[key] = previous
            pub.git(self.root, 'remote', 'set-url', '--push', 'origin', 'https://github.com/fixture/wrong.git')
            with self.assertRaises(pub.PublicationError):
                adapter.validate(self.root, self.config)

    def test_reviewed_deletion(self):
        self.publish()
        (self.root / 'README.md').unlink()
        self.publish()
        self.assertNotIn('README.md', pub.git(self.root, 'ls-tree', '-r', '--name-only', 'HEAD'))


def retire(work, manifest):
    # The independently selected project boundary is never supplied by a caller.
    boundary = ROOT / 'verification'
    short_run = (work.parent.parent == boundary and work.name == 'w'
                 and re.fullmatch(r'pub_[0-9a-f]{12}', work.parent.name))
    legacy_run = (work.parent.parent == boundary / 'docs_review/publisher_tests'
                  and work.name == 'work' and re.fullmatch(r'[0-9a-f]{32}', work.parent.name))
    if not (short_run or legacy_run):
        raise RuntimeError('Unexpected fixture boundary')
    # Extended syntax addresses the same validated Windows path, including old
    # fixtures whose teardown stopped during enumeration before any deletion.
    disk_work = Path('\\\\?\\' + str(work)) if os.name == 'nt' else work
    for p in (work, *work.parents):
        if p.is_symlink() or getattr(p.lstat(), 'st_file_attributes', 0) & 0x400:
            raise RuntimeError('Reparse ancestor; preserve for review')
        if p == ROOT:
            break
    entries = list(disk_work.rglob('*'))
    for p in (disk_work, *entries):
        if p.is_symlink() or getattr(p.lstat(), 'st_file_attributes', 0) & 0x400:
            raise RuntimeError('Reparse fixture; preserve for review')
    current = {str(p.relative_to(disk_work)): hashlib.sha256(p.read_bytes()).hexdigest()
               for p in entries if p.is_file()}
    if current != manifest:
        raise RuntimeError('Fixture identity changed; preserve for review')
    for name in manifest:
        file = disk_work / name
        # Git creates read-only loose objects on Windows; these are owned fixtures.
        if not file.stat().st_mode & stat.S_IWRITE:
            file.chmod(file.stat().st_mode | stat.S_IWRITE)
        file.unlink()
    for p in sorted((p for p in entries if p.is_dir()),
                    key=lambda p: len(p.parts), reverse=True):
        p.rmdir()
    disk_work.rmdir()


if __name__ == '__main__':
    names = unittest.defaultTestLoader.getTestCaseNames(PublisherTests)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=names, action='append')
    selected = parser.parse_args().case or names
    run_dir = ROOT / 'verification' / ('pub_' + uuid.uuid4().hex[:12])
    WORK = run_dir / 'w'
    WORK.mkdir(parents=True, exist_ok=False)
    result = None
    receipt = {'producer': 'tests/test_github_push.py', 'network': False,
               'scope': 'fresh Git fixtures only', 'central_exception':
               'Source project is outside configured central project_roots.',
               'byte_limit': 2000000, 'case_names': selected}
    try:
        result = unittest.TextTestRunner(verbosity=2).run(
            unittest.TestSuite(PublisherTests(name) for name in selected))
    finally:
        files = [p for p in WORK.rglob('*') if p.is_file()]
        manifest = {str(p.relative_to(WORK)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in files}
        receipt.update(files=len(files), bytes=sum(p.stat().st_size for p in files),
                       passed=bool(result and result.wasSuccessful()), removed=False)
        (run_dir / 'receipt.json').write_text(json.dumps(receipt, indent=2))
        retire(WORK, manifest)
        receipt['removed'] = not WORK.exists()
        (run_dir / 'receipt.json').write_text(json.dumps(receipt, indent=2))
    sys.exit(0 if result and result.wasSuccessful() else 1)
