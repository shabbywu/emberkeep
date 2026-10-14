"""Registry surface and object commands, independent of the native renderer."""
import asyncio
import inspect

import pytest

from game.bridge import Controller
from game.storage import SaveStore


class Registry:
    def __init__(self):
        self.functions = {}
        self.objects = {}

    def register(self, function):
        self.functions[function.__name__] = function
        return function

    def register_object(self, name, instance, *, members):
        self.objects[name] = instance, members


def test_explicit_api_surface_and_type_hints(tmp_path):
    controller, api = Controller(SaveStore(tmp_path)), Registry()
    controller.register_api(api)
    assert set(api.functions) == {'boot', 'new_run', 'move', 'whirl', 'cast_bolt', 'heal',
                                  'wait_turn', 'interact', 'choose_upgrade', 'set_paused',
                                  'save_game', 'load_game', 'set_language'}
    assert all(inspect.iscoroutinefunction(fn) for fn in api.functions.values())
    for fn in api.functions.values():
        signature = inspect.signature(fn)
        assert signature.return_annotation != inspect.Signature.empty
        assert all(p.annotation != inspect.Parameter.empty for p in signature.parameters.values())
    game, members = api.objects['game']
    assert game is controller.view
    assert {'move', 'whirl', 'cast_bolt', 'heal', 'wait_turn', 'interact', 'hero'} <= set(members)


def test_global_functions_and_live_instance_methods_share_engine(tmp_path):
    async def scenario():
        controller, api = Controller(SaveStore(tmp_path)), Registry()
        controller.register_api(api)
        game, _ = api.objects['game']
        hero = game.hero
        await api.functions['new_run'](19)
        await api.functions['wait_turn']()
        assert game.turn == 1
        await game.wait_turn()
        assert game.turn == 2
        assert hero.hp == controller.game.state['player']['hp']
        with pytest.raises(AttributeError): game.turn = 99
        with pytest.raises(AttributeError): hero.hp = 99
        await api.functions['save_game']()
        await api.functions['new_run'](42)
        assert game.hero is hero and game.seed == 42 and game.turn == 0
        with pytest.raises(ValueError): await game.move('heal')
    asyncio.run(scenario())
