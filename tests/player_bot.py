"""Acceptance player. Only reads the same fog-filtered snapshot as the UI.

Never changes game state, reveals a map, teleports, or grants resources.
"""
from collections import deque

MOVES = {(0, -1): 'up', (1, 0): 'right', (0, 1): 'down', (-1, 0): 'left'}
PRIORITIES = ['plate', 'siphon', 'heart', 'edge', 'flame', 'supply', 'haste', 'sight']


def choose_action(s, visits):
    if s['phase'] == 'upgrade':
        option = min(s['upgrades'], key=lambda u: PRIORITIES.index(u['id']))
        return 'choose_upgrade', [option['id']]
    p = s['player']
    pos = p['x'], p['y']
    rows = s['rows']
    enemies = s['enemies']
    occupied = {(e['x'], e['y']) for e in enemies}
    warning = {tuple(tile) for tile in s.get('warnings', [])}
    walkable = lambda c: 0 <= c[0] < s['width'] and 0 <= c[1] < s['height'] and rows[c[1]][c[0]] not in '# '
    neighbours = [(pos[0]+dx, pos[1]+dy) for dx, dy in MOVES]
    if pos in warning:
        safe = [c for c in neighbours if walkable(c) and c not in warning and c not in occupied]
        if safe:
            safe.sort(key=lambda c: (sum(abs(e['x']-c[0])+abs(e['y']-c[1]) <= 1 for e in enemies),
                                     visits.get((s['floor'], *c), 0)))
            c = safe[0]
            return 'move', [MOVES[c[0]-pos[0], c[1]-pos[1]]]
    if p['potions'] and p['hp'] <= p['max_hp']-16:
        return 'heal', []
    adjacent = [e for e in enemies if abs(e['x']-pos[0])+abs(e['y']-pos[1]) == 1]
    if adjacent and p['whirl_remaining'] == 0:
        return 'whirl', []
    ranged = [e for e in enemies if abs(e['x']-pos[0])+abs(e['y']-pos[1]) <= 4]
    if ranged and p['bolt_remaining'] == 0:
        enemy = min(ranged, key=lambda e: (0 if e['kind'] == 'cultist' else 1, e['hp']))
        return 'cast_bolt', [enemy['x'], enemy['y']]
    if adjacent:
        enemy = min(adjacent, key=lambda e: e['hp'])
        return 'move', [MOVES[enemy['x']-pos[0], enemy['y']-pos[1]]]

    queue, parents, distance = deque([pos]), {pos: None}, {pos: 0}
    while queue:
        a = queue.popleft()
        for dx, dy in MOVES:
            c = a[0]+dx, a[1]+dy
            if walkable(c) and c not in parents and c not in warning:
                parents[c], distance[c] = a, distance[a]+1
                queue.append(c)
    # Fight visible enemies before using stairs; earn enough upgrades for the boss.
    goals = [(e['x'], e['y']) for e in enemies if (e['x'], e['y']) in parents]
    if not goals:
        goals = [(i['x'], i['y']) for i in s['items'] if (i['x'], i['y']) in parents]
    if not goals and s['exit'] and tuple(s['exit']) in parents:
        goals = [tuple(s['exit'])]
    if not goals:
        goals = [c for c in parents if any(0 <= c[0]+dx < s['width'] and 0 <= c[1]+dy < s['height']
                                        and rows[c[1]+dy][c[0]+dx] == ' ' for dx, dy in MOVES)]
    goals = [c for c in goals if c != pos]
    if not goals:
        return 'wait_turn', []
    goal = min(goals, key=lambda c: distance[c]+visits.get((s['floor'], *c), 0)*2)
    step = goal
    while parents[step] != pos:
        step = parents[step]
    return 'move', [MOVES[step[0]-pos[0], step[1]-pos[1]]]


def play(game, seed, limit=2400):
    s, visits, reached = game.new(seed), {}, set()
    for _ in range(limit):
        reached.add(s['floor'])
        if s['phase'] in ('won', 'dead'):
            return s, reached
        key = s['floor'], s['player']['x'], s['player']['y']
        visits[key] = visits.get(key, 0)+1
        method, args = choose_action(s, visits)
        s = getattr(game, method)(*args)
    raise AssertionError(f'Player got stuck: seed={seed}, phase={s["phase"]}, turn={s["turn"]}, pos={key}')
