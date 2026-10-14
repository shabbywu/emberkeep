"""Versioned JSON saves with atomic replacement. No engine or UI dependency."""
import asyncio
import json
import os
from pathlib import Path
import tempfile

from .i18n import LocalizedError


class SaveStore:
    def __init__(self, directory=None):
        self.directory = Path(directory).expanduser() if directory else Path.home() / '.emberkeep'
        self.path = self.directory / 'save.json'

    def exists(self):
        return self.path.is_file()

    def _write(self, payload):
        self.directory.mkdir(parents=True, exist_ok=True)
        # Unique sibling temp files and replace also work on Windows.
        descriptor, name = tempfile.mkstemp(prefix='.save-', suffix='.tmp', dir=self.directory)
        try:
            with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                json.dump(payload, stream, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    async def save(self, payload):
        await asyncio.to_thread(self._write, payload)

    async def load(self):
        def read():
            if self.path.stat().st_size > 2_000_000:
                raise LocalizedError('error.large')
            with self.path.open(encoding='utf-8') as stream:
                return json.load(stream)
        try:
            return await asyncio.to_thread(read)
        except FileNotFoundError as exc:
            raise LocalizedError('error.missing') from exc
        except (json.JSONDecodeError, UnicodeError) as exc:
            raise LocalizedError('error.corrupt') from exc
