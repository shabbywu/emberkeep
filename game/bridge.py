"""Typed API and stable, read-only live proxies.

Registration entry point: Controller.register_api(), called by run.create_application().
All rule calls and Ultralight operations stay on the Python main thread.
"""
from __future__ import annotations

from .i18n import LocalizedError, LOCALES, catalog, localize_snapshot, translate

import asyncio
from typing import Any, Callable, TYPE_CHECKING
from functools import wraps

from .engine import Game, Snapshot
from .storage import SaveStore

if TYPE_CHECKING:
    from ultralight_py import API


def localized_errors(operation: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(operation)
    async def wrapped(self: Controller, *args: Any, **kwargs: Any) -> Any:
        try:
            return await operation(self, *args, **kwargs)
        except LocalizedError as exc:
            raise ValueError(translate(self.language, exc.key)) from exc
    return wrapped


class HeroView:
    """Getter-only character facade; never expose the mutable engine dictionary."""

    def __init__(self, game: Game) -> None:
        self._game: Game = game

    def _value(self, name: str, default: int = 0) -> int:
        return self._game.state['player'][name] if self._game.state else default

    @property
    def hp(self) -> int:
        return self._value('hp')

    @property
    def max_hp(self) -> int:
        return self._value('max_hp')

    @property
    def level(self) -> int:
        return self._value('level', 1)

    @property
    def attack(self) -> int:
        return self._value('attack')

    @property
    def armor(self) -> int:
        return self._value('armor')

    @property
    def potions(self) -> int:
        return self._value('potions')


class GameView:
    """One stable proxy whose properties read the current run, including after Load."""

    def __init__(self, game: Game) -> None:
        self._game: Game = game
        self._hero: HeroView = HeroView(game)

    @property
    def hero(self) -> HeroView:
        return self._hero

    @property
    def phase(self) -> str:
        return self._game.state['phase'] if self._game.state else 'menu'

    @property
    def floor(self) -> int:
        return self._game.state['floor'] if self._game.state else 0

    @property
    def turn(self) -> int:
        return self._game.state['turn'] if self._game.state else 0

    @property
    def seed(self) -> int:
        return self._game.state['seed'] if self._game.state else 0


class GameObject(GameView):
    """Live state + commands on an actual Python instance exported to JavaScript."""

    def __init__(self, controller: Controller) -> None:
        super().__init__(controller.game)
        self._controller: Controller = controller

    async def move(self, direction: str) -> Snapshot:
        return await self._controller.move(direction)

    async def whirl(self) -> Snapshot:
        return await self._controller.whirl()

    async def cast_bolt(self, x: int | None = None, y: int | None = None) -> Snapshot:
        return await self._controller.cast_bolt(x, y)

    async def heal(self) -> Snapshot:
        return await self._controller.heal()

    async def wait_turn(self) -> Snapshot:
        return await self._controller.wait_turn()

    async def interact(self, x: int, y: int) -> Snapshot:
        return await self._controller.interact(x, y)


class Controller:
    """Serialize API requests, calculate turns, and await atomic saves off-thread."""

    def __init__(self, store: SaveStore, seed: int | None = None, language: str | None = None) -> None:
        self.language: str = language or 'en'
        catalog(self.language)
        self.language_override: bool = language is not None
        self.game: Game = Game()
        self.view: GameObject = GameObject(self)
        self.store: SaveStore = store
        self.default_seed: int | None = seed
        self._lock: asyncio.Lock = asyncio.Lock()
        self.saved: bool = False
        self.save_error: str = ''

    def _response(self, snapshot: Snapshot | None = None) -> Snapshot:
        result = localize_snapshot(self.game.snapshot() if snapshot is None else snapshot, self.language)
        active = not self.game.state or self.game.state['phase'] not in ('won', 'dead')
        result.update(has_save=self.store.exists() and active, saved=self.saved, save_error=self.save_error)
        return result

    async def boot(self) -> Snapshot:
        result = self._response({'phase': 'menu', 'events': []})
        result.update(catalog=dict(catalog(self.language)), language_override=self.language_override)
        if result['has_save']:
            try:
                saved = await self.store.load()
                result['has_save'] = saved.get('state', {}).get('phase') not in ('won', 'dead')
            except (ValueError, OSError, AttributeError):
                pass
        return result

    async def _persist(self) -> None:
        try:
            await self.store.save(self.game.export())
            self.saved, self.save_error = True, ''
        except OSError as exc:
            self.saved, self.save_error = False, translate(self.language, 'error.save', reason=exc.strerror or str(exc))

    @localized_errors
    async def new_run(self, seed: int | None = None) -> Snapshot:
        async with self._lock:
            result = self.game.new(self.default_seed if seed is None else seed)
            await self._persist()
            return self._response(result)

    @localized_errors
    async def _run_turn(self, operation: Callable[..., Snapshot], *args: Any) -> Snapshot:
        async with self._lock:
            before = self.game.revision
            result = operation(*args)
            if self.game.revision != before:
                await self._persist()
            return self._response(result)

    async def move(self, direction: str) -> Snapshot:
        return await self._run_turn(self.game.move, direction)

    async def whirl(self) -> Snapshot:
        return await self._run_turn(self.game.whirl)

    async def cast_bolt(self, x: int | None = None, y: int | None = None) -> Snapshot:
        return await self._run_turn(self.game.cast_bolt, x, y)

    async def heal(self) -> Snapshot:
        return await self._run_turn(self.game.heal)

    async def wait_turn(self) -> Snapshot:
        return await self._run_turn(self.game.wait_turn)

    async def interact(self, x: int, y: int) -> Snapshot:
        return await self._run_turn(self.game.interact, x, y)

    @localized_errors
    async def choose_upgrade(self, id: str) -> Snapshot:
        async with self._lock:
            result = self.game.choose_upgrade(id)
            await self._persist()
            return self._response(result)

    @localized_errors
    async def set_paused(self, value: bool) -> Snapshot:
        async with self._lock:
            return self._response(self.game.pause(value))

    @localized_errors
    async def save_game(self) -> Snapshot:
        async with self._lock:
            await self._persist()
            if self.save_error:
                raise OSError(self.save_error)
            return self._response()

    @localized_errors
    async def load_game(self) -> Snapshot:
        async with self._lock:
            payload = await self.store.load()
            probe = Game()
            probe.restore(payload)
            if probe.state['phase'] in ('won', 'dead'):
                raise LocalizedError('error.finished')
            result = self.game.restore(payload)
            self.saved, self.save_error = True, ''
            return self._response(result)

    async def set_language(self, language: str) -> Snapshot:
        if language not in LOCALES:
            raise ValueError('Unsupported language: ' + str(language))
        async with self._lock:
            self.language = language
            # Switching a menu must not resume an in-memory paused adventure.
            result = self._response()
            result['events'] = []
            result['catalog'] = dict(catalog(language))
            return result

    def register_api(self, api: API) -> None:
        """Install host.game and thirteen explicit API functions before navigation.

        JS: host.move('right') -> Promise<Python dict proxy>
            host.game.whirl() -> call an actual Python instance method
            Python.to_value(await host.move('right')) -> rendering snapshot
            host.game.hero.hp -> live read-only Python property
        """
        api.register_object('game', self.view, members=[
            'hero', 'phase', 'floor', 'turn', 'seed',
            'move', 'whirl', 'cast_bolt', 'heal', 'wait_turn', 'interact',
        ])
        for function in (self.boot, self.new_run, self.choose_upgrade, self.set_paused, self.set_language):
            api.register(function)

        @api.register
        async def move(direction: str) -> Snapshot:
            return await self.move(direction)

        @api.register
        async def whirl() -> Snapshot:
            return await self.whirl()

        @api.register
        async def cast_bolt(x: int | None = None, y: int | None = None) -> Snapshot:
            return await self.cast_bolt(x, y)

        @api.register
        async def heal() -> Snapshot:
            return await self.heal()

        @api.register
        async def wait_turn() -> Snapshot:
            return await self.wait_turn()

        @api.register
        async def interact(x: int, y: int) -> Snapshot:
            return await self.interact(x, y)

        @api.register
        async def save_game() -> Snapshot:
            return await self.save_game()

        @api.register
        async def load_game() -> Snapshot:
            return await self.load_game()
