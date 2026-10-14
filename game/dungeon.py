"""Connected room-and-corridor dungeons and small, deterministic grid helpers."""
from collections import deque

WIDTH, HEIGHT, FLOORS = 33, 25, 4
DIRECTIONS = ((0, -1), (1, 0), (0, 1), (-1, 0))


def distances(rows, start, blocked=()):
    blocked = set(blocked)
    found, queue = {start: 0}, deque([start])
    while queue:
        x, y = queue.popleft()
        for dx, dy in DIRECTIONS:
            p = x + dx, y + dy
            if (0 <= p[0] < len(rows[0]) and 0 <= p[1] < len(rows)
                    and rows[p[1]][p[0]] not in ('#', ' ') and p not in found
                    and p not in blocked):
                found[p] = found[x, y] + 1
                queue.append(p)
    return found


def next_step(rows, start, goal, blocked=()):
    # Reverse BFS gives a stable tie break and never requires a hidden JS pathfinder.
    field = distances(rows, goal, set(blocked) - {start, goal})
    choices = [(start[0] + dx, start[1] + dy) for dx, dy in DIRECTIONS]
    choices = [p for p in choices if p in field and p not in blocked]
    if not choices:
        return None
    best = min(choices, key=lambda p: field[p])
    return best if field[best] < field.get(start, 9999) else None


def line_of_sight(rows, a, b):
    x, y = a
    bx, by = b
    dx, dy = abs(bx - x), abs(by - y)
    sx, sy = (1 if x < bx else -1), (1 if y < by else -1)
    error = dx - dy
    while (x, y) != (bx, by):
        e = error * 2
        if e > -dy:
            error -= dy
            x += sx
        if e < dx:
            error += dx
            y += sy
        if rows[y][x] == '#':
            # The first wall is visible; cells beyond it remain occluded.
            return (x, y) == (bx, by)
    return True


def generate(rng):
    grid = [['#'] * WIDTH for _ in range(HEIGHT)]
    rooms = []
    for _ in range(500):
        w, h = rng.randint(5, 8), rng.randint(4, 7)
        x, y = rng.randint(2, WIDTH - w - 2), rng.randint(2, HEIGHT - h - 2)
        if any(not (x + w < a or a + rw < x or y + h < b or b + rh < y)
               for a, b, rw, rh in rooms):
            continue
        rooms.append((x, y, w, h))
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                grid[yy][xx] = '.'
        if len(rooms) == 7:
            break
    if len(rooms) < 2:
        raise RuntimeError('无法生成地牢，请换一个种子。')
    centers = [(x + w // 2, y + h // 2) for x, y, w, h in rooms]
    pairs = list(zip(centers, centers[1:]))
    if len(centers) > 3:
        pairs.append((centers[0], centers[-2]))
    for (x, y), (tx, ty) in pairs:
        horizontal_first = rng.choice((True, False))
        while (x, y) != (tx, ty):
            grid[y][x] = '.'
            if (horizontal_first and x != tx) or y == ty:
                x += 1 if x < tx else -1
            else:
                y += 1 if y < ty else -1
        grid[y][x] = '.'
    rows = [''.join(row) for row in grid]
    start = centers[0]
    field = distances(rows, start)
    exit_ = max(centers[1:], key=lambda p: field[p])
    grid[exit_[1]][exit_[0]] = '>'
    return [''.join(row) for row in grid], start, exit_, rooms
