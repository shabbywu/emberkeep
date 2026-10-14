"""Language must change presentation without changing rules, saves or RNG."""
import asyncio
from copy import deepcopy
from string import Formatter

import pytest

from game.bridge import Controller
from game.engine import Game
from game.i18n import catalog, localize_snapshot
from game.storage import SaveStore


def test_catalog_keys_and_placeholders_match():
    en, zh = catalog('en'), catalog('zh-CN')
    assert en.keys() == zh.keys()
    for key in en:
        fields = lambda text: {field for _, field, _, _ in Formatter().parse(text) if field}
        assert fields(en[key]) == fields(zh[key]), key


def test_language_switch_preserves_simulation_and_history(tmp_path):
    async def scenario():
        controller = Controller(SaveStore(tmp_path), language='en')
        before = await controller.new_run(19)
        payload = controller.game.export()
        revision = controller.game.revision
        chinese = await controller.set_language('zh-CN')
        assert chinese['messages'] != before['messages']
        assert chinese['floor_name'] == '遗忘的门廊'
        assert controller.game.export() == payload
        assert controller.game.revision == revision
        english = await controller.set_language('en')
        assert english['messages'] == before['messages']
        assert english['events'] == []
        await controller.set_paused(True)
        await controller.set_language('zh-CN')
        assert controller.game.state['paused']
        with pytest.raises(ValueError, match='移动方向'):
            await controller.move('invalid')
        with pytest.raises(ValueError): await controller.set_language('fr')
        assert controller.language == 'zh-CN'
        await controller.load_game()
        assert controller.game.export() == payload
    asyncio.run(scenario())


def test_legacy_text_save_retains_rules_and_rng():
    game = Game()
    game.new(19)
    payload = game.export()
    payload['state']['messages'] = ['灯火尚未熄灭。']
    for enemy in payload['state']['enemies']: enemy['name'] = '旧名称'
    restored = Game()
    restored.restore(payload)
    actual = restored.export()
    assert actual['rng'] == payload['rng']
    expected = deepcopy(payload['state'])
    expected['messages'] = [{'key': 'log.continued', 'params': {}}]
    for enemy in expected['enemies']: enemy.pop('name')
    assert actual['state'] == expected
    assert 'Adventure continued' in localize_snapshot(restored.snapshot(), 'en')['messages'][0]


def test_bad_message_cannot_replace_run():
    game = Game()
    game.new(42)
    before = game.export()
    malformed = deepcopy(before)
    malformed['state']['messages'] = [{'key': 'log.kill', 'params': {}}]
    with pytest.raises(ValueError): game.restore(malformed)
    assert game.export() == before


def test_all_content_translates():
    from game.engine import ENEMIES, UPGRADES
    game = Game()
    game.new(19)
    snapshot = game.snapshot()
    snapshot['enemies'] = [{'kind': key} for key in ENEMIES]
    snapshot['upgrades'] = [{'id': key} for key in UPGRADES]
    for language in ('en', 'zh-CN'):
        translated = localize_snapshot(snapshot, language)
        assert all(e['name'] for e in translated['enemies'])
        assert all(u['name'] and u['desc'] and u['tag'] for u in translated['upgrades'])
