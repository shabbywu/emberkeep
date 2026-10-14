"""Prepare native DLL search and windowed streams before application imports."""
import os
from pathlib import Path
import sys
import tempfile

if sys.platform == 'win32':
    # Retain directory handles for the application's lifetime. The wheel's
    # delvewheel patch adds a directory without retaining the returned handle.
    _dll_directories = []
    for name in ('ultralight_py', 'ultralight_py.libs'):
        directory = Path(sys._MEIPASS) / name
        if directory.is_dir():
            _dll_directories.append(os.add_dll_directory(str(directory)))

if sys.stdout is None or sys.stderr is None:
    try:
        directory = Path.home() / '.emberkeep'
        directory.mkdir(parents=True, exist_ok=True)
        stream = (directory / 'emberkeep.log').open('a', encoding='utf-8', buffering=1)
    except OSError:
        stream = tempfile.TemporaryFile(mode='w+', encoding='utf-8')
    if sys.stdout is None:
        sys.stdout = stream
    if sys.stderr is None:
        sys.stderr = stream
