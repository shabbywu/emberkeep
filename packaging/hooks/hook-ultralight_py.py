"""Keep Ultralight's native libraries and Windows delvewheel layout intact."""
from PyInstaller.compat import is_win
from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_delvewheel_libs_directory,
    collect_dynamic_libs,
    collect_submodules,
    copy_metadata,
)

datas = collect_data_files('ultralight_py') + copy_metadata('ultralight-py')
binaries = collect_dynamic_libs('ultralight_py')
hiddenimports = collect_submodules(
    'ultralight_py', filter=lambda name: not name.startswith('ultralight_py.integrations.tkinter')
)
if is_win:
    datas, binaries = collect_delvewheel_libs_directory(
        'ultralight_py', datas=datas, binaries=binaries
    )
