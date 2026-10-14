"""Shared offline catalogs; presentation language never enters simulation or saves."""
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path
from typing import Any

LOCALES = ('en', 'zh-CN')
CATALOG_ROOT = Path(__file__).resolve().parents[1] / 'assets' / 'locales'


@lru_cache(maxsize=2)
def catalog(language: str) -> dict[str, str]:
    if language not in LOCALES:
        raise ValueError('Unsupported language: ' + str(language))
    return json.loads((CATALOG_ROOT / (language + '.json')).read_text(encoding='utf-8'))


def translate(language: str, key: str, **params: Any) -> str:
    return catalog(language)[key].format(**params)


class LocalizedError(ValueError):
    """A rule/storage error carrying a catalog key, translated by the bridge."""
    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(key)


def valid_message(value: Any) -> bool:
    if not isinstance(value, dict) or not isinstance(value.get('params'), dict):
        return False
    key = value.get('key')
    if not isinstance(key, str) or not key.startswith('log.') or key not in catalog('en'):
        return False
    try:
        catalog('en')[key].format(**value['params'])
        for name, parameter in value['params'].items():
            if type(parameter) not in (str, int):
                return False
            if name in ('enemy', 'name', 'upgrade') and parameter not in catalog('en'):
                return False
        return True
    except (KeyError, ValueError, TypeError):
        return False


def localize_snapshot(snapshot: dict[str, Any], language: str) -> dict[str, Any]:
    result = deepcopy(snapshot)
    if 'floor_name' in result:
        result['floor_name'] = translate(language, result['floor_name'])
    for enemy in result.get('enemies', []):
        enemy['name'] = translate(language, 'enemy.' + enemy['kind'])
    for upgrade in result.get('upgrades', []):
        for field in ('name', 'desc', 'tag'):
            upgrade[field] = translate(language, 'upgrade.' + upgrade['id'] + '.' + field)
    result['messages'] = []
    for message in snapshot.get('messages', []):
        params = {key: translate(language, value) if key in ('enemy', 'name', 'upgrade') else value
                  for key, value in message['params'].items()}
        result['messages'].append(translate(language, message['key'], **params))
    result['language'] = language
    return result
