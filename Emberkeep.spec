# Build with: python -m PyInstaller --clean --noconfirm Emberkeep.spec
from pathlib import Path
import sys

try:
    import tomllib
except ImportError:
    import tomli as tomllib

root = Path(SPECPATH)
project_version = tomllib.loads((root / 'pyproject.toml').read_text(encoding='utf-8'))['project']['version']

a = Analysis(
    [str(root / 'run.py')],
    pathex=[str(root)],
    binaries=[],
    datas=[
        (str(root / 'assets'), 'assets'),
        (str(root / 'LICENSE'), '.'),
        (str(root / 'packaging' / 'README.txt'), '.'),
    ],
    hiddenimports=[],
    hookspath=[str(root / 'packaging' / 'hooks')],
    runtime_hooks=[str(root / 'packaging' / 'windowed_logging.py')],
    excludes=['tkinter'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Emberkeep',
    debug=False,
    strip=False,
    upx=False,
    console=False,
    target_arch='arm64' if sys.platform == 'darwin' else None,
    codesign_identity=None,
)
collection = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='Emberkeep')
if sys.platform == 'darwin':
    app = BUNDLE(
        collection,
        name='Emberkeep.app',
        bundle_identifier='org.emberkeep.game',
        info_plist={
            'CFBundleShortVersionString': project_version,
            'CFBundleVersion': project_version,
            'NSHighResolutionCapable': True,
        },
    )
