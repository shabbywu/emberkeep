import asyncio
from copy import deepcopy
import json
import random
import pytest
from game.bridge import Controller, GameView
from game.dungeon import DIRECTIONS, FLOORS, HEIGHT, WIDTH, distances, generate
from game.engine import Game
from game.storage import SaveStore
from tests.player_bot import play

def perform(game, intention, *coordinates):
    """Test sequence adapter; the engine itself only exposes explicit methods."""
    if intention in ('up', 'right', 'down', 'left'):
        return game.move(intention)
    method = {'wait': 'wait_turn', 'bolt': 'cast_bolt', 'heal': 'heal', 'whirl': 'whirl'}[intention]
    return getattr(game, method)(*coordinates)


def arena(kind='slime', x=12, y=10):
    """Small controlled encounters for rule tests, never used for campaign acceptance."""
    game = Game()
    game.new(19)
    s = game.state
    s['rows'] = ['#' * WIDTH] + ['#' + '.' * (WIDTH - 2) + '#' for _ in range(HEIGHT - 2)] + ['#' * WIDTH]
    s['rows'][22] = s['rows'][22][:30] + '>' + s['rows'][22][31:]
    s['exit'] = [30, 22]
    s['player']['x'], s['player']['y'] = (10, 10)
    s['enemies'], s['items'], s['seen'] = ([], [], [])
    game._spawn(kind, x, y)
    game._reveal()
    return game

@pytest.mark.parametrize('seed', range(100))
def test_connected_generation(seed):
    rows, start, exit_, _ = generate(random.Random(seed))
    reachable = distances(rows, start)
    assert exit_ in reachable
    assert sum((c != '#' for row in rows for c in row)) == len(reachable)
    assert len(rows) == HEIGHT and all((len(row) == WIDTH for row in rows))
    assert all((c == '#' for c in rows[0] + rows[-1]))

def test_deterministic_actions():
    a, b = (Game(), Game())
    assert a.new(42) == b.new(42)
    for command in ['wait', 'down', 'left', 'bolt', 'heal', 'right', 'whirl', 'wait']:
        assert perform(a, command) == perform(b, command)
    assert a.export() == b.export()

def test_invalid_actions_and_pause_do_not_take_turn():
    game = arena(x=20)
    game.state['rows'][9] = game.state['rows'][9][:10] + '#' + game.state['rows'][9][11:]
    for action in ('up', 'heal', 'whirl', 'bolt'):
        assert perform(game, action)['turn'] == 0
    game.pause(True)
    assert game.move('right')['turn'] == 0
    game.pause(False)
    assert game.wait_turn()['turn'] == 1
    with pytest.raises(ValueError):
        game.move('nope')
    with pytest.raises(ValueError):
        game.move({})
    with pytest.raises(ValueError):
        game.cast_bolt(True, 2)
    with pytest.raises(ValueError):
        game.interact(True, 2)
    with pytest.raises(ValueError):
        game.new('seed')

def test_mouse_actions_have_same_rules_as_keyboard():
    a, b = (arena(x=11), arena(x=11))
    assert a.move('right') == b.interact(11, 10)
    a, b = (arena(x=13), arena(x=13))
    assert a.cast_bolt(13, 10) == b.interact(13, 10)

def test_slow_slime_and_skeleton_chase():
    slime, skeleton = (arena('slime', x=13), arena('skeleton', x=13))
    assert slime.wait_turn()['enemies'][0]['x'] == 13
    assert skeleton.wait_turn()['enemies'][0]['x'] == 12
    assert slime.wait_turn()['enemies'][0]['x'] == 12
    assert skeleton.wait_turn()['enemies'][0]['x'] == 11

def test_cultist_warning_is_dodgeable_and_not_instant_damage():
    game = arena('cultist', x=13)
    before = game.state['player']['hp']
    s = game.wait_turn()
    assert s['enemies'][0]['intent'] == [[10, 10]]
    assert s['player']['hp'] == before
    s = game.move('down')
    assert s['player']['hp'] == before
    assert s['enemies'][0]['intent'] == []
    game = arena('cultist', x=13)
    game.wait_turn()
    assert game.wait_turn()['player']['hp'] == before - 3

def test_skill_cooldowns_and_line_of_sight():
    game = arena('skeleton', x=13)
    s = game.cast_bolt()
    assert s['turn'] == 1 and s['player']['bolt_remaining'] == 3
    assert game.cast_bolt()['turn'] == 1
    for _ in range(3):
        s = game.wait_turn()
    assert s['player']['bolt_remaining'] == 0
    game = arena('skeleton', x=13)
    row = game.state['rows'][10]
    game.state['rows'][10] = row[:12] + '#' + row[13:]
    assert game.cast_bolt()['turn'] == 0

def test_whirl_hits_all_adjacent_targets():
    game = arena('slime', x=11)
    game._spawn('slime', 10, 11)
    s = game.whirl()
    assert s['kills'] == 2 and s['turn'] == 1
    assert s['player']['whirl_remaining'] == 4

def test_upgrade_state_and_remaining_experience():
    game = arena(x=20)
    game.state['player']['xp'] = 30
    s = game.wait_turn()
    assert s['phase'] == 'upgrade' and len(s['upgrades']) == 3
    assert game.wait_turn()['turn'] == s['turn']
    old_hp = s['player']['max_hp']
    game.state['upgrades'] = ['heart', 'plate', 'edge']
    s = game.choose_upgrade('heart')
    assert s['player']['level'] == 2 and s['player']['max_hp'] == old_hp + 8
    assert s['phase'] == 'upgrade'
    game.pause(True)
    with pytest.raises(ValueError):
        game.choose_upgrade(s['upgrades'][0]['id'])
    game.pause(False)
    with pytest.raises(ValueError):
        game.choose_upgrade('not_offered')

def test_boss_warning_and_second_phase():
    game = arena('warden', x=13)
    game.state['floor'] = 4
    game.state['turn'] = 2
    s = game.wait_turn()
    assert s['enemies'][0]['intent']
    assert s['player']['hp'] == 42
    assert game.move('left')['player']['hp'] == 42
    game.state['enemies'][0]['hp'] = 20
    s = game.wait_turn()
    assert s['enemies'][0]['rage'] is True

def test_boss_seals_exit_and_finish_is_terminal():
    game = arena('warden', x=13)
    s = game.state
    s['floor'] = 4
    s['player']['x'], s['player']['y'] = (29, 22)
    result = game.move('right')
    assert result['phase'] == 'playing'
    s['enemies'] = []
    result = game.wait_turn()
    assert result['phase'] == 'won'
    assert game.wait_turn()['turn'] == result['turn']

def test_fog_and_snapshot_are_not_backing_state():
    game = Game()
    s = game.new(19)
    assert ' ' in ''.join(s['rows'])
    assert all((e['y'] * WIDTH + e['x'] in s['visible'] for e in s['enemies']))
    s['player']['hp'] = 999
    s['rows'][0] = 'cheat'
    assert game.state['player']['hp'] == 42
    assert len(game.state['rows'][0]) == WIDTH

def test_first_wall_is_visible_but_occludes_tiles_behind_it():
    game = arena(x=20)
    row = game.state['rows'][10]
    game.state['rows'][10] = row[:12] + '#' + row[13:]
    game._reveal()
    s = game.snapshot()
    assert (12, 10) in game.visible()
    assert (13, 10) not in game.visible()
    assert s['rows'][10][12] == '#'

def test_read_only_nested_view_updates_after_new_and_restore():
    game = Game()
    view = GameView(game)
    hero = view.hero
    game.new(7)
    assert hero.hp == 42 and view.floor == 1
    with pytest.raises(AttributeError):
        hero.hp = 999
    with pytest.raises(AttributeError):
        view.turn = 999
    game.wait_turn()
    assert view.turn == 1
    game.new(42)
    assert view.hero is hero and view.seed == 42 and (view.turn == 0)

def test_atomic_async_save_and_rng_restore(tmp_path):

    async def scenario():
        original = arena('skeleton', x=14)
        store = SaveStore(tmp_path)
        await store.save(original.export())
        restored = Game()
        restored.restore(await store.load())
        assert original.export() == restored.export()
        for action in ('bolt', 'wait', 'down', 'right', 'wait'):
            left, right = (perform(original, action), perform(restored, action))
            left.pop('revision')
            right.pop('revision')
            assert left == right
        assert not list(tmp_path.glob('*.tmp'))
    asyncio.run(scenario())

def test_corrupt_save_does_not_replace_run(tmp_path):

    async def scenario():
        controller = Controller(SaveStore(tmp_path))
        await controller.new_run(19)
        before = controller.game.export()
        controller.store.path.write_text('{bad', encoding='utf-8')
        with pytest.raises(ValueError):
            await controller.load_game()
        assert controller.game.export() == before
        assert controller.store.path.read_text() == '{bad'
        invalid = deepcopy(before)
        invalid['state']['player']['hp'] = -10
        with pytest.raises(ValueError):
            controller.game.restore(invalid)
        assert controller.game.export() == before
        invalid['format_version'] = 999
        with pytest.raises(ValueError):
            controller.game.restore(invalid)
    asyncio.run(scenario())

def test_failed_atomic_replace_keeps_previous_save(tmp_path, monkeypatch):

    async def scenario():
        store = SaveStore(tmp_path)
        await store.save({'good': 1})

        def fail(*args):
            raise OSError('disk failure')
        monkeypatch.setattr('game.storage.os.replace', fail)
        with pytest.raises(OSError):
            await store.save({'good': 2})
        assert await store.load() == {'good': 1}
        assert not list(tmp_path.glob('.save-*'))
    asyncio.run(scenario())

def test_controller_serializes_actions_and_reports_io_failures(tmp_path, monkeypatch):

    async def scenario():
        controller = Controller(SaveStore(tmp_path))
        await controller.new_run(42)
        await asyncio.gather(*(controller.wait_turn() for _ in range(5)))
        assert controller.game.state['turn'] == 5
        assert (await controller.store.load())['state']['turn'] == 5

        async def fail(payload):
            raise OSError('disk full')
        monkeypatch.setattr(controller.store, 'save', fail)
        result = await controller.wait_turn()
        assert result['turn'] == 6 and (not result['saved']) and result['save_error']
    asyncio.run(scenario())

@pytest.mark.parametrize('seed', [7, 19, 42])
def test_full_campaign_uses_only_visible_snapshots(seed):
    result, reached = play(Game(), seed)
    assert result['phase'] == 'won', (seed, result['floor'], result['turn'], result['messages'])
    assert reached == {1, 2, 3, 4}
    assert result['kills'] >= 15 and result['player']['level'] >= 3

def test_natural_death():
    game = Game()
    s = game.new(7)
    from tests.player_bot import choose_action
    visits = {}
    for _ in range(2000):
        p = s['player']
        if any((abs(e['x'] - p['x']) + abs(e['y'] - p['y']) <= 4 for e in s['enemies'])):
            break
        key = (s['floor'], s['player']['x'], s['player']['y'])
        visits[key] = visits.get(key, 0) + 1
        method, args = choose_action(s, visits)
        s = getattr(game, method)(*args)
    assert s['enemies']
    for _ in range(150):
        if s['phase'] == 'dead':
            break
        s = game.wait_turn()
    assert s['phase'] == 'dead' and s['player']['hp'] == 0
