"""Authoritative turn simulation. No Ultralight, JS, files, or wall-clock timers."""
from copy import deepcopy
import random
import secrets
from typing import Any

from .i18n import LocalizedError, valid_message

from .dungeon import (DIRECTIONS, FLOORS, HEIGHT, WIDTH, generate, line_of_sight,
                      next_step)

ENEMIES = {
    'slime': {'hp': 8, 'attack': 3, 'armor': 0, 'xp': 2},
    'skeleton': {'hp': 12, 'attack': 4, 'armor': 1, 'xp': 3},
    'cultist': {'hp': 10, 'attack': 4, 'armor': 0, 'xp': 3},
    'warden': {'hp': 56, 'attack': 7, 'armor': 1, 'xp': 12},
}
UPGRADES = {
    'edge': {'icon': 'sword'},
    'heart': {'icon': 'heart'},
    'plate': {'icon': 'shield'},
    'flame': {'icon': 'bolt'},
    'haste': {'icon': 'whirl'},
    'supply': {'icon': 'potion'},
    'siphon': {'icon': 'torch'},
    'sight': {'icon': 'torch'},
}
Snapshot = dict[str, Any]

FLOOR_KEYS = ['floor.' + str(i) for i in range(1, FLOORS + 1)]


def tuples(value):
    return tuple(tuples(x) for x in value) if isinstance(value, list) else value


class Game:
    def __init__(self) -> None:
        self.state: dict[str, Any] | None = None
        self.rng = random.Random()
        self.events = []
        self.revision = 0

    def _event(self, kind, **data):
        self.events.append({'kind': kind, **data})

    def _say(self, key: str, **params: Any) -> None:
        self.state['messages'] = (self.state['messages'] + [{'key': key, 'params': params}])[-8:]

    def _begin(self):
        self.events = []

    def _end(self, consumed=False):
        if consumed:
            self.revision += 1
        return self.snapshot()

    def new(self, seed: int | None = None) -> Snapshot:
        if seed is None:
            seed = secrets.randbelow(2**31)
        if type(seed) is not int or not 0 <= seed < 2**31:
            raise LocalizedError('error.seed')
        self.rng = random.Random(seed)
        self._begin()
        self.state = {
            'seed': seed, 'floor': 1, 'turn': 0, 'kills': 0, 'gold': 0,
            'phase': 'playing', 'paused': False, 'next_id': 1,
            'player': {'x': 0, 'y': 0, 'hp': 42, 'max_hp': 42, 'attack': 6,
                       'armor': 1, 'potions': 3, 'level': 1, 'xp': 0,
                       'xp_next': 7, 'sight': 6, 'siphon': 0, 'bolt': 10,
                       'whirl_cd': 4, 'bolt_cd': 3, 'whirl_ready': 0,
                       'bolt_ready': 0},
            'messages': [], 'upgrades': [], 'enemies': [], 'items': [], 'seen': [],
        }
        self._floor()
        self._say('log.start')
        self.revision += 1
        return self.snapshot()

    def _floor(self):
        s = self.state
        rows, start, exit_, rooms = generate(self.rng)
        s.update(rows=rows, exit=list(exit_), seen=[], enemies=[], items=[], upgrades=[])
        s['player']['x'], s['player']['y'] = start
        s['player']['whirl_ready'] = s['player']['bolt_ready'] = s['turn']
        cells = [(x, y) for rx, ry, w, h in rooms[1:]
                 for y in range(ry, ry + h) for x in range(rx, rx + w)
                 if (x, y) != exit_ and abs(x - start[0]) + abs(y - start[1]) > 5]
        self.rng.shuffle(cells)
        boss_cell = None
        if s['floor'] == FLOORS:
            boss_cell = next((exit_[0] + dx, exit_[1] + dy) for dx, dy in DIRECTIONS
                             if rows[exit_[1] + dy][exit_[0] + dx] == '.')
            cells = [p for p in cells if p != boss_cell]
        count = min(5 + s['floor'], len(cells) // 2)
        # From floor two, each of the three behaviours is always represented.
        kinds = ['slime'] * count if s['floor'] == 1 else ['slime', 'skeleton', 'cultist']
        while len(kinds) < count:
            kinds.append(self.rng.choice(['slime', 'skeleton', 'cultist']))
        for kind in kinds:
            self._spawn(kind, *cells.pop())
        if boss_cell:
            self._spawn('warden', *boss_cell)
        for i in range(min(7, len(cells))):
            x, y = cells.pop()
            s['items'].append({'x': x, 'y': y, 'kind': 'potion' if i % 3 == 0 else 'chest'})
        self._reveal()
        self._say('log.floor', floor=s['floor'], name='floor.' + str(s['floor']))
        self._event('floor', floor=s['floor'])

    def _spawn(self, kind, x, y):
        s = self.state
        spec = ENEMIES[kind]
        strength = max(0, s['floor'] - 2) if kind != 'warden' else 0
        s['enemies'].append({'id': s['next_id'], 'kind': kind, 'x': x, 'y': y,
                             **spec, 'hp': spec['hp'] + strength * 2,
                             'max_hp': spec['hp'] + strength * 2, 'intent': [],
                             'awake': False, 'rage': False})
        s['next_id'] += 1

    def visible(self) -> set[tuple[int, int]]:
        if not self.state:
            return set()
        s, p = self.state, self.state['player']
        a = p['x'], p['y']
        radius = p['sight']
        return {(x, y) for y in range(max(0, a[1] - radius), min(HEIGHT, a[1] + radius + 1))
                for x in range(max(0, a[0] - radius), min(WIDTH, a[0] + radius + 1))
                if (x-a[0])**2 + (y-a[1])**2 <= radius**2
                and line_of_sight(s['rows'], a, (x, y))}

    def _reveal(self):
        s = self.state
        s['seen'] = sorted(set(s['seen']) | {y * WIDTH + x for x, y in self.visible()})

    def snapshot(self) -> Snapshot:
        if not self.state:
            return {'phase': 'menu', 'revision': self.revision, 'events': []}
        s = self.state
        visible = self.visible()
        seen = set(s['seen'])
        p = dict(s['player'])
        p['whirl_remaining'] = max(0, p['whirl_ready'] - s['turn'])
        p['bolt_remaining'] = max(0, p['bolt_ready'] - s['turn'])
        return {'phase': s['phase'], 'paused': s['paused'], 'floor': s['floor'],
                'floor_name': FLOOR_KEYS[s['floor']-1], 'floors': FLOORS,
                'seed': s['seed'], 'turn': s['turn'], 'kills': s['kills'], 'gold': s['gold'],
                'score': self.score(), 'width': WIDTH, 'height': HEIGHT,
                'rows': [''.join(c if y*WIDTH+x in seen else ' ' for x, c in enumerate(row))
                         for y, row in enumerate(s['rows'])],
                'visible': sorted(y*WIDTH+x for x, y in visible), 'player': p,
                'enemies': deepcopy([e for e in s['enemies'] if (e['x'], e['y']) in visible]),
                'items': deepcopy([i for i in s['items'] if (i['x'], i['y']) in visible]),
                'warnings': [list(tile) for e in s['enemies'] for tile in e['intent']
                             if tuple(tile) in visible],
                'exit': list(s['exit']) if s['exit'][1]*WIDTH+s['exit'][0] in seen else None,
                'upgrades': [{'id': key, **UPGRADES[key]} for key in s['upgrades']],
                'messages': deepcopy(s['messages']), 'events': deepcopy(self.events),
                'revision': self.revision}

    def score(self) -> int:
        if not self.state:
            return 0
        s = self.state
        return max(0, (s['floor']-1)*200+s['kills']*40+s['gold']*5
                   +s['player']['level']*50-s['turn']//2+(800 if s['phase']=='won' else 0))

    def _enemy(self, x, y):
        return next((e for e in self.state['enemies'] if (e['x'], e['y']) == (x, y)), None)

    def _damage_enemy(self, enemy, damage, spell=False):
        damage = max(1, damage - (0 if spell else enemy['armor']))
        enemy['hp'] -= damage
        self._event('hit', x=enemy['x'], y=enemy['y'], amount=damage, target=enemy['id'])
        if enemy['hp'] <= 0:
            s, p = self.state, self.state['player']
            s['enemies'].remove(enemy)
            s['kills'] += 1
            s['gold'] += 3 if enemy['kind'] != 'warden' else 25
            p['xp'] += enemy['xp']
            p['hp'] = min(p['max_hp'], p['hp'] + p['siphon'])
            self._event('death', x=enemy['x'], y=enemy['y'], enemy=enemy['kind'])
            self._say('log.kill', enemy='enemy.' + enemy['kind'], xp=enemy['xp'])
            if enemy['kind'] == 'warden':
                self._say('log.boss_down')

    def _hurt(self, amount, attacker):
        p = self.state['player']
        damage = max(1, amount - p['armor'])
        p['hp'] = max(0, p['hp'] - damage)
        self._event('hurt', x=p['x'], y=p['y'], amount=damage)
        self._say('log.hurt', enemy='enemy.' + attacker, damage=damage)
        if not p['hp']:
            self.state['phase'] = 'dead'
            self.state['paused'] = False
            self._say('log.death')

    def _pickup(self):
        s, p = self.state, self.state['player']
        for item in list(s['items']):
            if (item['x'], item['y']) != (p['x'], p['y']):
                continue
            s['items'].remove(item)
            if item['kind'] == 'potion':
                p['potions'] += 1
                self._say('log.potion')
            else:
                gold = self.rng.randint(5, 12)
                s['gold'] += gold
                p['xp'] += 2
                self._say('log.chest', gold=gold)
            self._event('pickup', x=p['x'], y=p['y'], item=item['kind'])

    def _upgrade_check(self):
        s, p = self.state, self.state['player']
        if s['phase'] == 'playing' and p['xp'] >= p['xp_next']:
            s['phase'] = 'upgrade'
            s['upgrades'] = self.rng.sample(list(UPGRADES), 3)
            self._say('log.upgrade')

    def choose_upgrade(self, key: str) -> Snapshot:
        self._begin()
        s = self.state
        if not s or s['phase'] != 'upgrade':
            raise LocalizedError('error.no_upgrade')
        if s['paused']:
            raise LocalizedError('error.paused_upgrade')
        if key not in s['upgrades']:
            raise LocalizedError('error.upgrade')
        p = s['player']
        p['xp'] -= p['xp_next']
        p['level'] += 1
        p['xp_next'] = 7 + (p['level']-1)*4
        if key == 'edge': p['attack'] += 2
        elif key == 'heart':
            p['max_hp'] += 8
            p['hp'] = min(p['max_hp'], p['hp']+14)
        elif key == 'plate': p['armor'] += 1
        elif key == 'flame': p['bolt'] += 3
        elif key == 'haste':
            p['whirl_cd'] = max(2, p['whirl_cd']-1)
            p['bolt_cd'] = max(2, p['bolt_cd']-1)
        elif key == 'supply':
            p['potions'] += 2
            p['hp'] = min(p['max_hp'], p['hp']+6)
        elif key == 'siphon': p['siphon'] += 2
        elif key == 'sight':
            p['sight'] += 1
            p['max_hp'] += 4
            p['hp'] += 4
        # A little recovery makes each level-up feel good regardless of its option.
        p['hp'] = min(p['max_hp'], p['hp']+4)
        s['phase'], s['upgrades'] = 'playing', []
        self._say('log.level', level=p['level'], upgrade='upgrade.' + key + '.name')
        self._event('upgrade', upgrade=key)
        self._upgrade_check()
        self._reveal()
        return self._end(True)

    def pause(self, value: bool) -> Snapshot:
        if type(value) is not bool:
            raise LocalizedError('error.pause')
        self._begin()
        if self.state and self.state['phase'] in ('playing', 'upgrade'):
            self.state['paused'] = value
        return self._end()

    def _start_turn(self) -> bool:
        self._begin()
        return bool(self.state and self.state['phase'] == 'playing' and not self.state['paused'])

    def _melee(self, enemy: dict[str, Any]) -> None:
        p = self.state['player']
        damage = p['attack'] + self.rng.randint(0, 2)
        critical = self.rng.random() < .12
        if critical:
            damage += p['attack']//2
        self._event('melee', x=p['x'], y=p['y'], tx=enemy['x'], ty=enemy['y'], critical=critical)
        self._damage_enemy(enemy, damage)

    def move(self, direction: str) -> Snapshot:
        moves = {'up': (0, -1), 'right': (1, 0), 'down': (0, 1), 'left': (-1, 0)}
        if not isinstance(direction, str) or direction not in moves:
            raise LocalizedError('error.direction')
        if not self._start_turn():
            return self._end()
        s, p = self.state, self.state['player']
        origin = p['x'], p['y']
        dx, dy = moves[direction]
        target = origin[0]+dx, origin[1]+dy
        if not (0 <= target[0] < WIDTH and 0 <= target[1] < HEIGHT) or s['rows'][target[1]][target[0]] == '#':
            self._say('log.wall')
            self._event('bump', x=p['x'], y=p['y'])
            return self._end()
        enemy = self._enemy(*target)
        if enemy:
            self._melee(enemy)
        else:
            p['x'], p['y'] = target
            self._event('move', x=origin[0], y=origin[1], tx=p['x'], ty=p['y'])
            self._pickup()
        return self._finish_turn()

    def whirl(self) -> Snapshot:
        if not self._start_turn():
            return self._end()
        s, p = self.state, self.state['player']
        victims = [e for e in s['enemies'] if abs(e['x']-p['x'])+abs(e['y']-p['y']) == 1]
        if p['whirl_ready'] > s['turn'] or not victims:
            self._say('log.whirl_wait' if p['whirl_ready'] > s['turn'] else 'log.no_adjacent')
            return self._end()
        for enemy in victims:
            self._damage_enemy(enemy, p['attack']+4)
        p['whirl_ready'] = s['turn'] + 1 + p['whirl_cd']
        self._event('whirl', x=p['x'], y=p['y'])
        return self._finish_turn()

    def cast_bolt(self, x: int | None = None, y: int | None = None) -> Snapshot:
        if not self._start_turn():
            return self._end()
        if x is not None or y is not None:
            if type(x) is not int or type(y) is not int or not (0 <= x < WIDTH and 0 <= y < HEIGHT):
                raise LocalizedError('error.target')
        s, p = self.state, self.state['player']
        if p['bolt_ready'] > s['turn']:
            self._say('log.bolt_wait')
            return self._end()
        origin = p['x'], p['y']
        targets = [e for e in s['enemies'] if (e['x'], e['y']) in self.visible()
                   and abs(e['x']-p['x'])+abs(e['y']-p['y']) <= 4
                   and line_of_sight(s['rows'], origin, (e['x'], e['y']))]
        if x is not None or y is not None:
            targets = [e for e in targets if (e['x'], e['y']) == (x, y)]
        if not targets:
            self._say('log.no_target')
            return self._end()
        enemy = min(targets, key=lambda e: (abs(e['x']-p['x'])+abs(e['y']-p['y']), e['id']))
        self._event('bolt', x=p['x'], y=p['y'], tx=enemy['x'], ty=enemy['y'])
        self._damage_enemy(enemy, p['bolt']+self.rng.randint(0, 2), spell=True)
        p['bolt_ready'] = s['turn'] + 1 + p['bolt_cd']
        return self._finish_turn()

    def heal(self) -> Snapshot:
        if not self._start_turn():
            return self._end()
        p = self.state['player']
        if not p['potions'] or p['hp'] == p['max_hp']:
            self._say('log.no_potion' if not p['potions'] else 'log.full_hp')
            return self._end()
        amount = min(18, p['max_hp']-p['hp'])
        p['potions'] -= 1
        p['hp'] += amount
        self._event('heal', x=p['x'], y=p['y'], amount=amount)
        self._say('log.heal', amount=amount)
        return self._finish_turn()

    def wait_turn(self) -> Snapshot:
        if not self._start_turn():
            return self._end()
        return self._finish_turn()

    def interact(self, x: int, y: int) -> Snapshot:
        if not self._start_turn():
            return self._end()
        if type(x) is not int or type(y) is not int or not (0 <= x < WIDTH and 0 <= y < HEIGHT):
            raise LocalizedError('error.coordinates')
        if (x, y) not in self.visible():
            self._say('log.unseen')
            return self._end()
        p = self.state['player']
        delta = x-p['x'], y-p['y']
        moves = {'up': (0, -1), 'right': (1, 0), 'down': (0, 1), 'left': (-1, 0)}
        if delta in DIRECTIONS:
            return self.move(next(key for key, value in moves.items() if value == delta))
        if self._enemy(x, y):
            return self.cast_bolt(x, y)
        if delta == (0, 0):
            return self.wait_turn()
        self._say('log.mouse')
        return self._end()

    def _finish_turn(self) -> Snapshot:
        """The one shared boundary: time, stairs, enemy response, visibility, growth."""
        s, p = self.state, self.state['player']
        s['turn'] += 1
        self._reveal()
        if [p['x'], p['y']] == s['exit']:
            if s['floor'] < FLOORS:
                s['floor'] += 1
                p['hp'] = min(p['max_hp'], p['hp']+8)
                self._floor()
                self._upgrade_check()
                return self._end(True)
            if not any(e['kind'] == 'warden' for e in s['enemies']):
                s['phase'] = 'won'
                self._say('log.victory')
                self._event('win')
                return self._end(True)
            self._say('log.locked')
        self._enemy_turn()
        self._reveal()
        self._upgrade_check()
        return self._end(True)

    def _enemy_turn(self):
        s, p = self.state, self.state['player']
        occupied = {(e['x'], e['y']) for e in s['enemies']}
        for enemy in list(s['enemies']):
            if s['phase'] == 'dead':
                break
            a, b = (enemy['x'], enemy['y']), (p['x'], p['y'])
            distance = abs(a[0]-b[0])+abs(a[1]-b[1])
            sight = distance <= 8 and line_of_sight(s['rows'], a, b)
            # Waking is persistent, but an enemy does not chase through the entire map.
            if sight:
                enemy['awake'] = True
            if enemy['intent']:
                tiles = enemy['intent']
                enemy['intent'] = []
                self._event('enemy_spell', tiles=tiles, enemy=enemy['kind'])
                if list(b) in tiles:
                    self._hurt(enemy['attack'] + (2 if enemy['rage'] else 0), enemy['kind'])
                continue
            if not enemy['awake'] or distance > 10:
                continue
            kind = enemy['kind']
            if kind == 'slime' and s['turn'] % 2:
                continue
            if kind == 'warden':
                rage = enemy['hp'] <= enemy['max_hp']//2
                if rage and not enemy['rage']:
                    enemy['rage'] = True
                    self._say('log.rage')
                    self._event('rage', x=a[0], y=a[1])
                period = 2 if rage else 3
                if sight and s['turn'] % period == 0:
                    # A strip leaves a perpendicular escape route in one turn.
                    # A 3x3 warning centred on the hero would be impossible to dodge.
                    radius = 2 if rage else 1
                    vertical = abs(a[0]-b[0]) >= abs(a[1]-b[1])
                    enemy['intent'] = [[b[0] if vertical else b[0]+d,
                                        b[1]+d if vertical else b[1]]
                                       for d in range(-radius, radius+1)
                                       if 0 < (b[0] if vertical else b[0]+d) < WIDTH-1
                                       and 0 < (b[1]+d if vertical else b[1]) < HEIGHT-1
                                       and s['rows'][b[1]+d if vertical else b[1]][b[0] if vertical else b[0]+d] != '#']
                    self._event('warn', tiles=enemy['intent'])
                    self._say('log.warning')
                    continue
            if kind == 'cultist' and sight and 2 <= distance <= 4:
                enemy['intent'] = [list(b)]
                self._event('warn', tiles=enemy['intent'])
                continue
            if distance == 1 and kind != 'cultist':
                self._event('enemy_melee', x=a[0], y=a[1], tx=b[0], ty=b[1])
                self._hurt(enemy['attack'], enemy['kind'])
                continue
            blocked = occupied - {a}
            if kind == 'cultist' and distance < 3:
                candidates = [(a[0]+dx, a[1]+dy) for dx, dy in DIRECTIONS]
                candidates = [c for c in candidates if 0 < c[0] < WIDTH-1 and 0 < c[1] < HEIGHT-1
                              and s['rows'][c[1]][c[0]] != '#' and c not in blocked and c != b]
                target = max(candidates, key=lambda c: abs(c[0]-b[0])+abs(c[1]-b[1]), default=None)
                if not target and distance == 1:
                    self._hurt(enemy['attack'], enemy['kind'])
            else:
                target = next_step(s['rows'], a, b, blocked)
            if target and target != b:
                occupied.remove(a)
                enemy['x'], enemy['y'] = target
                occupied.add(target)
                self._event('enemy_move', id=enemy['id'], x=a[0], y=a[1], tx=target[0], ty=target[1])

    def export(self) -> dict[str, Any]:
        if not self.state:
            raise LocalizedError('error.no_run')
        return {'format_version': 1, 'state': deepcopy(self.state), 'rng': self.rng.getstate()}

    def restore(self, payload: dict[str, Any]) -> Snapshot:
        # Validate before committing: a bad file cannot replace the active run.
        if not isinstance(payload, dict) or payload.get('format_version') != 1:
            raise LocalizedError('error.version')
        def require(condition):
            if not condition:
                raise LocalizedError('error.corrupt')
        try:
            s = deepcopy(payload['state'])
            rng = random.Random()
            rng.setstate(tuples(payload['rng']))
            p = s['player']
            require(s['phase'] in ('playing', 'upgrade', 'won', 'dead'))
            require(type(s['seed']) is int and 0 <= s['seed'] < 2**31)
            require(type(s['floor']) is int and 1 <= s['floor'] <= FLOORS)
            require(type(s['turn']) is int and s['turn'] >= 0)
            require(len(s['rows']) == HEIGHT and all(len(row) == WIDTH for row in s['rows']))
            require(all(c in '#.>' for row in s['rows'] for c in row))
            require(type(p['x']) is int and type(p['y']) is int)
            require(0 <= p['x'] < WIDTH and 0 <= p['y'] < HEIGHT)
            require(s['rows'][p['y']][p['x']] != '#')
            for key in ('hp', 'max_hp', 'attack', 'armor', 'potions', 'level', 'xp', 'xp_next',
                        'sight', 'siphon', 'bolt', 'whirl_cd', 'bolt_cd', 'whirl_ready', 'bolt_ready'):
                require(type(p[key]) is int and p[key] >= 0)
            require(0 <= p['hp'] <= p['max_hp'] and p['max_hp'] > 0 and p['xp_next'] > 0)
            require(p['level'] > 0 and 1 <= p['sight'] <= WIDTH)
            for key in ('enemies', 'items', 'seen', 'messages', 'upgrades', 'exit'):
                require(isinstance(s[key], list))
            require(len(s['exit']) == 2 and s['rows'][s['exit'][1]][s['exit'][0]] == '>')
            ids, cells = set(), set()
            for e in s['enemies']:
                require(e['kind'] in ENEMIES and e['id'] not in ids)
                ids.add(e['id'])
                cell = e['x'], e['y']
                require(cell not in cells and cell != (p['x'], p['y']))
                cells.add(cell)
                require(0 <= cell[0] < WIDTH and 0 <= cell[1] < HEIGHT)
                require(s['rows'][cell[1]][cell[0]] != '#')
                require(0 < e['hp'] <= e['max_hp'] and isinstance(e['intent'], list))
                for tile in e['intent']:
                    require(len(tile) == 2 and 0 <= tile[0] < WIDTH and 0 <= tile[1] < HEIGHT)
            for item in s['items']:
                require(item['kind'] in ('potion', 'chest'))
                require(0 <= item['x'] < WIDTH and 0 <= item['y'] < HEIGHT)
                require(s['rows'][item['y']][item['x']] != '#')
            require(all(type(i) is int and 0 <= i < WIDTH*HEIGHT for i in s['seen']))
            require(all(isinstance(message, str) or valid_message(message) for message in s['messages']))
            if any(isinstance(message, str) for message in s['messages']):
                s['messages'] = [{'key': 'log.continued', 'params': {}}]
            for enemy in s['enemies']:
                enemy.pop('name', None)
            require(all(key in UPGRADES for key in s['upgrades']))
            require(s['phase'] != 'upgrade' or len(s['upgrades']) == 3)
            require(s['phase'] != 'dead' or p['hp'] == 0)
            require(type(s['next_id']) is int and s['next_id'] > max(ids, default=0))
            for key in ('kills', 'gold'):
                require(type(s[key]) is int and s[key] >= 0)
        except (KeyError, TypeError, IndexError, ValueError, AssertionError) as exc:
            raise LocalizedError('error.corrupt') from exc
        s['paused'] = False
        self.state, self.rng = s, rng
        self.events = []
        self.revision += 1
        return self.snapshot()
