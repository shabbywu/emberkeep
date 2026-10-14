"""Build, archive and smoke-test the same desktop bundle that users download."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

try:
    import tomllib
except ImportError:
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[1]


def release_version(tag=None, build_id=None):
    project = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))['project']
    version = project['version']
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('The desktop release version must use X.Y.Z')
    if tag is not None and tag != f'v{version}':
        raise ValueError(f'Release tag must be v{version}, got {tag!r}')
    if build_id is not None:
        if not re.fullmatch(r'[0-9a-fA-F]{7,40}', build_id):
            raise ValueError('Build ID must be a Git commit SHA (7 to 40 hex digits)')
        version += f'-{build_id[:7]}'
    return version


def target_platform():
    machine = platform.machine().lower()
    if sys.platform == 'win32' and machine in ('amd64', 'x86_64'):
        return 'windows-x64'
    if sys.platform == 'darwin' and machine == 'arm64':
        return 'macos-arm64'
    raise RuntimeError('Build on Windows x64 or macOS Apple Silicon')


def archive_bundle(target, version):
    output = ROOT / 'dist' / 'releases'
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f'Emberkeep-{version}-{target}.zip'
    if target == 'macos-arm64':
        shutil.copy2(ROOT / 'packaging' / 'README.txt', ROOT / 'dist' / 'README.txt')
        shutil.copy2(ROOT / 'LICENSE', ROOT / 'dist' / 'LICENSE')
        # ZIP must retain PyInstaller's links between Resources and Frameworks.
        # Remove only a previous generated archive so ZIP cannot retain stale entries.
        archive.unlink(missing_ok=True)
        subprocess.run(
            ['zip', '-qry', '--symlinks', str(archive), 'Emberkeep.app', 'README.txt', 'LICENSE'],
            cwd=ROOT / 'dist', check=True,
        )
    else:
        bundle = ROOT / 'dist' / 'Emberkeep'
        shutil.copy2(ROOT / 'packaging' / 'README.txt', bundle / 'README.txt')
        shutil.copy2(ROOT / 'LICENSE', bundle / 'LICENSE')
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as zipped:
            for path in sorted(bundle.rglob('*')):
                if path.is_file():
                    zipped.write(path, path.relative_to(ROOT / 'dist'))
    return archive


def verify_archive(archive, target):
    diagnostics = ROOT / 'build' / 'diagnostics'
    diagnostics.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='emberkeep-release-') as directory:
        extracted = Path(directory) / 'extracted'
        extracted.mkdir()
        if target == 'macos-arm64':
            subprocess.run(['ditto', '-x', '-k', str(archive), str(extracted)], check=True)
            app = extracted / 'Emberkeep.app'
            subprocess.run(['codesign', '--verify', '--deep', '--strict', str(app)], check=True)
            executable = app / 'Contents' / 'MacOS' / 'Emberkeep'
            if not os.access(executable, os.X_OK):
                raise RuntimeError('Extracted macOS executable lost its execute permission')
        else:
            with zipfile.ZipFile(archive) as zipped:
                zipped.extractall(extracted)
            executable = extracted / 'Emberkeep' / 'Emberkeep.exe'
        environment = os.environ.copy()
        for key in ('PYTHONPATH', 'PYTHONHOME'):
            environment.pop(key, None)
        # Isolate Windows log output and saves from the developer's real adventure.
        environment['USERPROFILE'] = directory
        environment['HOME'] = directory
        for language in ('en', 'zh-CN'):
            report = diagnostics / f'smoke-{language}.json'
            report.unlink(missing_ok=True)
            log = diagnostics / f'smoke-{language}.log'
            command = [str(executable), '--smoke', '--cpu', '--lang', language,
                       '--smoke-report', str(report)]
            try:
                with log.open('w', encoding='utf-8') as stream:
                    result = subprocess.run(
                        command, cwd=directory, env=environment, timeout=180,
                        stdout=stream, stderr=subprocess.STDOUT,
                    )
                if result.returncode != 0:
                    raise RuntimeError(f'{language} smoke exited with {result.returncode}; see {log}')
                payload = json.loads(report.read_text(encoding='utf-8'))
                if payload.get('passed') is not True or payload.get('language') != language:
                    raise RuntimeError(f'{language} smoke report failed: {payload}')
                print(f'Extracted bundle smoke PASS: {language}', flush=True)
            finally:
                windowed_log = Path(directory) / '.emberkeep' / 'emberkeep.log'
                if windowed_log.exists():
                    shutil.copy2(windowed_log, diagnostics / 'windowed.log')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--tag', help='Require this tag to match v<project version>')
    mode.add_argument('--build-id', help='Append the short commit SHA for a manual build')
    args = parser.parse_args()
    version = release_version(args.tag, args.build_id)
    target = target_platform()
    subprocess.run(
        [sys.executable, '-m', 'PyInstaller', '--clean', '--noconfirm', str(ROOT / 'Emberkeep.spec')],
        cwd=ROOT, check=True,
    )
    archive = archive_bundle(target, version)
    verify_archive(archive, target)
    hasher = hashlib.sha256()
    with archive.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            hasher.update(chunk)
    digest = hasher.hexdigest()
    archive.with_suffix('.zip.sha256').write_text(f'{digest}  {archive.name}\n', encoding='utf-8')
    print(f'Verified release bundle: {archive}', flush=True)


if __name__ == '__main__':
    main()
