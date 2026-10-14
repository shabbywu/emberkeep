"""Real AppCore acceptance: visible-state player + native key/mouse input.

Run separately from pytest, on a graphical desktop. Screenshots use CPU View pixels.
The test has no Playwright/browser shim and never changes authoritative game state.
"""
import argparse
import asyncio
import json
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from game.bridge import Controller
from game.storage import SaveStore
from run import create_application
from tests.player_bot import choose_action


async def acceptance(cpu, output, seeds):
    from ultralight_py import KeyCode
    from ultralight_py.images import to_pillow
    screenshot_dir = output/'screenshots'
    report_dir = output/'reports'
    with tempfile.TemporaryDirectory(prefix='emberkeep-acceptance-') as folder:
        controller = Controller(SaveStore(folder))
        app, window, api = create_application(controller, cpu, Path(folder)/'cache')
        view = window.view
        failures, captures = [], set()
        view.on('console', lambda message: failures.append(message)
                if message.get('level') in ('error', 3) else None)
        task = asyncio.create_task(app.run_async())
        started = time.monotonic()
        report = {'runtime': 'ultralight-py 0.5.0', 'renderer': 'CPU' if cpu else 'AppCore default',
                  'platform': sys.platform, 'campaigns': [], 'checks': [], 'screenshots': []}

        def snapshot():
            return view.evaluate('window.EmberUI.snapshot()')

        async def idle_after(previous_calls):
            try:
                await view.wait_until(lambda: view.evaluate(
                    f'window.EmberUI.diagnostics().calls>{previous_calls} && !window.EmberUI.diagnostics().busy'), timeout=12)
            except TimeoutError as exc:
                details = view.evaluate('window.EmberUI.diagnostics()')
                details['active_element'] = view.evaluate('document.activeElement.id')
                raise AssertionError(f'Input did not reach API: {details}') from exc
            status = view.evaluate('window.EmberUI.diagnostics()')
            assert not status['error'], status
            return snapshot()

        async def key(code):
            calls = view.evaluate('window.EmberUI.diagnostics().calls')
            view.focus()
            view.key_down(code)
            view.key_up(code)
            return await idle_after(calls)

        async def click_element(id, changes=True):
            position = view.evaluate(f'(function(){{const r=document.getElementById({json.dumps(id)}).getBoundingClientRect();return [Math.round(r.left+r.width/2),Math.round(r.top+r.height/2)]}})()')
            calls = view.evaluate('window.EmberUI.diagnostics().calls')
            view.focus()
            view.click(*position)
            return await idle_after(calls) if changes else snapshot()

        async def click_tile(x, y):
            s = snapshot()
            p = s['player']
            cx = max(0, min(s['width']-23, p['x']-11))
            cy = max(0, min(s['height']-17, p['y']-8))
            rect = view.evaluate('window.EmberUI.diagnostics().canvas.rect')
            xx = round(rect['left']+(x-cx+.5)*rect['width']/23)
            yy = round(rect['top']+(y-cy+.5)*rect['height']/17)
            calls = view.evaluate('window.EmberUI.diagnostics().calls')
            view.focus()
            view.click(xx, yy)
            return await idle_after(calls)

        async def capture(name, force=False):
            if not cpu or (name in captures and not force):
                return
            await asyncio.sleep(.28)
            frame = view.copy_pixels()
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            to_pillow(frame).save(screenshot_dir/f'{name}.png')
            captures.add(name)
            if name not in report['screenshots']:
                report['screenshots'].append(name)

        async def command(method, args):
            if snapshot().get('paused'):
                # A real OS focus loss correctly pauses the game. The acceptance
                # player continues through the same button a human would use.
                await click_element('resumeBtn')
            if method == 'choose_upgrade':
                s = snapshot()
                index = next(i for i, u in enumerate(s['upgrades']) if u['id'] == args[0])
                return await key([KeyCode.GK_1, KeyCode.GK_2, KeyCode.GK_3][index])
            action = args[0] if method == 'move' else method
            if method == 'cast_bolt' and len(args) == 2:
                s = snapshot()
                p = s['player']
                if abs(args[0]-p['x'])+abs(args[1]-p['y']) > 1:
                    return await click_tile(args[0], args[1])
            codes = {'up': KeyCode.GK_W, 'right': KeyCode.GK_D, 'down': KeyCode.GK_S,
                     'left': KeyCode.GK_A, 'whirl': KeyCode.GK_Q, 'cast_bolt': KeyCode.GK_E,
                     'heal': KeyCode.GK_R, 'wait_turn': KeyCode.GK_SPACE}
            return await key(codes[action])

        try:
            await view.wait_ready(timeout=20)
            await view.wait_until(lambda: view.evaluate('!!window.EMBER_READY'), timeout=20)
            assert view.evaluate('document.fonts.check("12px Ember")')
            assert view.evaluate('host.game.hero === host.game.hero')
            await capture('menu')
            report['checks'].append('bundled atlas/font and native menu')
            for seed in seeds:
                if snapshot()['phase'] != 'menu':
                    await click_element('endingMenuBtn')
                await click_element('seedInput', changes=False)
                view.input_text(str(seed))
                s = await click_element('startBtn')
                assert s['seed'] == seed and s['phase'] == 'playing'
                if seed == seeds[0]:
                    p = s['player']
                    directions = [((0, -1), KeyCode.GK_W), ((1, 0), KeyCode.GK_D),
                                  ((0, 1), KeyCode.GK_S), ((-1, 0), KeyCode.GK_A)]
                    ((dx, dy), code) = next((d, k) for d, k in directions
                                           if s['rows'][p['y']+d[1]][p['x']+d[0]] not in '# ')
                    origin = p['x'], p['y']
                    s = await key(code)
                    assert (s['player']['x'], s['player']['y']) == (origin[0]+dx, origin[1]+dy), (origin, dx, dy, s, view.evaluate('document.activeElement.tagName'))
                    s = await click_tile(*origin)
                    assert (s['player']['x'], s['player']['y']) == origin
                    assert s['turn'] == 2
                    # Legacy DOM fields test the fallback for native systems omitting code.
                    calls = view.evaluate('window.EmberUI.diagnostics().calls')
                    view.evaluate('window.dispatchEvent(new KeyboardEvent("keydown",{key:" ",code:"",keyCode:32,bubbles:true}))')
                    s = await idle_after(calls)
                    assert s['turn'] == 3
                    s = await key(KeyCode.GK_ESCAPE)
                    assert s['paused']
                    turn = s['turn']
                    view.key_down(KeyCode.GK_SPACE); view.key_up(KeyCode.GK_SPACE)
                    await asyncio.sleep(.04)
                    assert snapshot()['turn'] == turn
                    await capture('pause')
                    s = await click_element('resumeBtn')
                    assert not s['paused']
                    s = await key(KeyCode.GK_F5)
                    saved = await controller.store.load()
                    assert saved['state']['turn'] == turn
                    s = await view.evaluate_async('window.EmberUI.invoke("load_game")')
                    assert s['turn'] == turn
                    assert view.evaluate('(function(){try{host.game.hero.hp=999;return false}catch(e){return true}})()')
                    assert view.evaluate('host.game.hero.hp') == s['player']['hp']
                    await view.evaluate_async('window.EmberUI.invoke("boot")')
                    assert not view.evaluate('document.getElementById("continueBtn").disabled')
                    s = await click_element('continueBtn')
                    assert s['turn'] == turn
                    # Focus loss pauses; focus gain does not resume unattended.
                    calls = view.evaluate('window.EmberUI.diagnostics().calls')
                    view.evaluate('window.dispatchEvent(new Event("blur"))')
                    s = await idle_after(calls)
                    assert s['paused']
                    s = await key(KeyCode.GK_ESCAPE)
                    assert not s['paused']
                    report['checks'].extend(['native WASD and mouse map coordinates', 'legacy key fallback',
                                             'pause blocks turns', 'F5 save and menu Continue',
                                             'live proxy rejects writes', 'blur pauses'])
                visits, floors, operations = {}, set(), 0
                while s['phase'] not in ('won', 'dead') and operations < 2400:
                    floors.add(s['floor'])
                    k = s['floor'], s['player']['x'], s['player']['y']
                    visits[k] = visits.get(k, 0)+1
                    if s['phase'] == 'upgrade': await capture('upgrades')
                    if s['floor'] >= 2 and s['phase'] == 'playing' and s['enemies']:
                        await capture('gameplay')
                    if any(e['kind'] == 'warden' for e in s['enemies']): await capture('boss')
                    method, args = choose_action(s, visits)
                    s = await command(method, args)
                    operations += 1
                    if operations % 100 == 0:
                        print(f'NATIVE seed={seed} turn={s["turn"]} floor={s["floor"]} hp={s["player"]["hp"]}', flush=True)
                assert s['phase'] == 'won', (seed, s['phase'], s['floor'], s['turn'], s['messages'])
                assert floors == {1, 2, 3, 4}
                await capture('victory')
                report['campaigns'].append({'seed': seed, 'outcome': s['phase'], 'turns': s['turn'],
                                            'kills': s['kills'], 'level': s['player']['level'],
                                            'hp': s['player']['hp'], 'inputs': operations})
                print(f'NATIVE WIN seed={seed} turns={s["turn"]} kills={s["kills"]}', flush=True)
            await click_element('endingMenuBtn')
            assert view.evaluate('document.getElementById("continueBtn").disabled')
            await click_element('seedInput', changes=False)
            view.input_text('7')
            s = await click_element('startBtn')
            visits = {}
            for _ in range(500):
                p = s['player']
                if any(abs(e['x']-p['x'])+abs(e['y']-p['y']) <= 4 for e in s['enemies']): break
                k = s['floor'], s['player']['x'], s['player']['y']
                visits[k] = visits.get(k, 0)+1
                method, args = choose_action(s, visits)
                s = await command(method, args)
            assert s['enemies']
            for _ in range(150):
                if s['phase'] == 'dead': break
                s = await command('wait_turn', [])
            assert s['phase'] == 'dead' and s['player']['hp'] == 0
            await capture('failure')
            report['campaigns'].append({'seed': 7, 'outcome': 'dead', 'turns': s['turn']})
            report['checks'].append('natural death and terminal save cannot Continue')
            # Real windows at each logical size; AppCore owns the root View's dimensions.
            # Do not fake this by resizing a root View which its Panel immediately restores.
            if cpu:
                for width, height in [(800, 600), (1280, 800), (1600, 1000)]:
                    extra = app.create_window(width, height, title=f'Emberkeep layout {width}×{height}')
                    api.attach(extra.view)
                    extra.view.load_url('file:///index.html')
                    try:
                        await extra.view.wait_ready(timeout=15)
                        await extra.view.wait_until(lambda: extra.view.evaluate('!!window.EMBER_READY'), timeout=15)
                        await extra.view.evaluate_async('window.EmberUI.invoke("wait_turn")')
                        await asyncio.sleep(.2)
                        layout = extra.view.evaluate('(function(){const r=document.getElementById("card").getBoundingClientRect();const b=document.getElementById("board").getBoundingClientRect();return {width:innerWidth,height:innerHeight,card:r.width,body:document.body.scrollWidth,canvas:b.width}})()')
                        assert layout['width'] == extra.width
                        assert layout['height'] == extra.height
                        assert 100 < layout['card'] < width and layout['body'] <= width
                        assert layout['canvas'] > 100
                        name = f'layout-{width}x{height}'
                        to_pillow(extra.view.copy_pixels()).save(screenshot_dir/f'{name}.png')
                        report['screenshots'].append(name)
                    finally:
                        extra.close()
                report['checks'].append('actual 800x600, 1280x800, 1600x1000 windows and DPI layout')
            assert not view.evaluate('window.EmberUI.diagnostics().error')
            assert not failures, failures
            report['seconds'] = round(time.monotonic()-started, 2)
            report['manual_physical_input_tested'] = False
            report_dir.mkdir(parents=True, exist_ok=True)
            (report_dir/('native-cpu.json' if cpu else 'native-default.json')).write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            print('NATIVE ACCEPTANCE PASS', json.dumps(report, ensure_ascii=False), flush=True)
        finally:
            app.close()
            await task
            api.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cpu', action='store_true')
    parser.add_argument('--output', type=Path, default=ROOT/'docs')
    parser.add_argument('--seeds', type=int, nargs='+', default=[7, 19, 42])
    args = parser.parse_args()
    asyncio.run(acceptance(args.cpu, args.output, args.seeds))
