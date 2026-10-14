# Emberkeep

English · [简体中文](README.zh-CN.md)

Emberkeep is a desktop pixel roguelike with turn based combat. Carry a lantern through four randomly generated dungeon floors, find the stairs, defeat the Lightless Warden, and escape into daylight.

Slimes move slowly, Bone Sentinels pursue you, and Ash Cultists keep their distance while charging spells. Fight with melee attacks, Whirlwind, Ember Bolt and healing potions. Gain experience and choose one of three random upgrades. The game includes a main menu, pause screen, upgrades, victory and defeat screens, and save continuation.

It is also a demo of `ultralight-py 0.5.0`: Python owns the rules; JavaScript draws the Canvas and UI. Registered functions, live object proxies and Promises connect them.

![Native gameplay](docs/screenshots/gameplay-en.png)

## Run

Requires Python 3.10+ and a graphical desktop.

```bash
python -m pip install -r requirements.txt
python run.py
```

Alternatively, use `uv run python run.py`. Options: `--cpu` for CPU rendering, `--seed 19` for a fixed dungeon seed, and `--data-dir ./local-save` for a custom save directory.

Choose English or 简体中文 in the top right corner; your preference is remembered. `--lang en` or `--lang zh-CN` overrides that preference at startup.

The atlas, font and page resources ship with the game. No server or network is needed. Every valid action automatically saves to `~/.emberkeep/save.json`. The pause menu lets you save and return; the main menu continues an unfinished adventure.

## Controls

| Input | Action |
| --- | --- |
| WASD / arrows | Move; bump enemies to strike |
| Mouse click | Move to adjacent ground; melee adjacent enemies; cast Ember Bolt at distant enemies |
| Q / E / R | Whirlwind / Ember Bolt / healing potion |
| Space | Wait one turn |
| 1 / 2 / 3 | Choose an upgrade |
| Esc / F5 | Pause / save |
| F3 | Bridge diagnostics |

Red warning tiles are struck next turn: move away. Walls and unavailable skills do not consume a turn. Losing window focus pauses the adventure; resume when you return.

## Implementation

- [`game/engine.py`](game/engine.py): state, combat, AI, growth and endings. Explicit action methods share one turn boundary.
- [`game/bridge.py`](game/bridge.py): typed bridge. `Controller.register_api()` installs 13 explicit APIs and exposes live state and instance commands through `register_object`.
- [`run.py`](run.py): native AppCore window, asyncio loop and `resource_loader`; [`assets/`](assets/) supplies rendering and UI.
- [`game/storage.py`](game/storage.py): asynchronous, versioned JSON saves with RNG state and atomic replacement.

The keyboard calls registered functions such as `host.move('right')`; the skill bar and mouse call instance methods such as `host.game.whirl()`. The HUD reads live, read-only properties such as `host.game.hero.hp`; `Python.to_value()` copies render snapshots. See [`assets/bridge.d.ts`](assets/bridge.d.ts) for the frontend interface.

Text lives in [`assets/locales/`](assets/locales/). Python returns translated display snapshots; logs store keys and parameters. Language changes consume no turns and leave RNG untouched. Older Chinese saves retain gameplay state; their text history is replaced by a continuation notice.

## Tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python run.py --smoke
```

Rule tests, three native winning campaigns and a natural defeat were validated with the real 0.5.0 runtime. See [validation](docs/VALIDATION.md) for results and limits, and [`docs/screenshots/`](docs/screenshots/) for native captures.

Code and original pixel art are MIT licensed. The bundled Noto Sans SC font uses OFL; see `assets/font-license.txt`. ultralight-py and Ultralight/AppCore retain their own licenses.
