"""Verify stable DOM during real moves, delayed feedback, language and save errors."""
import asyncio
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from game.bridge import Controller
from game.storage import SaveStore
from run import create_application


async def main():
    with tempfile.TemporaryDirectory(prefix='emberkeep-html-') as directory:
        store = SaveStore(directory)
        controller = Controller(store, language='en')
        app, window, api = create_application(controller, True, Path(directory) / 'cache')
        task = asyncio.create_task(app.run_async())
        view = window.view

        async def invoke(name, args=None):
            return await view.evaluate_async(f'EmberUI.invoke({json.dumps(name)},{json.dumps(args or [])})')

        try:
            await view.wait_ready(timeout=20)
            await view.wait_until(lambda: view.evaluate('!!window.EMBER_READY'), timeout=20)
            assert view.evaluate('Alpine.version') == '3.17.4'
            # Language switches retain typed seeds and focus in the generated menu.
            view.evaluate("document.getElementById('seedInput').value='19';document.getElementById('seedInput').focus();document.getElementById('languageZh').click()")
            await view.wait_until(lambda: view.evaluate("document.documentElement.lang==='zh-CN'&&!EmberUI.diagnostics().busy"), timeout=10)
            assert view.evaluate("document.getElementById('seedInput').value") == '19'
            assert view.evaluate('document.activeElement.id') == 'seedInput'
            await invoke('set_language', ['en'])
            snapshot = await invoke('new_run', [19])
            assert view.evaluate("document.getElementById('saveStatus').textContent") == 'Saved'
            x, y = snapshot['player']['x'], snapshot['player']['y']
            direction = None
            for name, dx, dy, reverse in [('right', 1, 0, 'left'), ('left', -1, 0, 'right'),
                                          ('down', 0, 1, 'up'), ('up', 0, -1, 'down')]:
                nx, ny = x + dx, y + dy
                if snapshot['rows'][ny][nx] != '.':
                    continue
                if any(item['x'] == nx and item['y'] == ny for item in snapshot['items']):
                    continue
                if any(abs(enemy['x'] - nx) + abs(enemy['y'] - ny) < 8 for enemy in snapshot['enemies']):
                    continue
                direction = name, reverse
                break
            assert direction, 'Seed 19 should have a safe adjacent corridor for movement checks'
            view.evaluate("""(()=>{
              window.stableMutations=[]; window.turnMutations=0;
              window.logNodes=[...document.querySelectorAll('#logLines p')];
              window.canvasNode=document.getElementById('board');
              window.htmlObserver=new MutationObserver(records=>stableMutations.push(...records.map(r=>r.type)));
              for(const node of document.querySelectorAll('[data-i18n],#languageSwitch,#saveStatus,#hpText,#hpFill,#xpText,#xpFill,#logLines,#board'))
                htmlObserver.observe(node,{childList:true,subtree:true,attributes:true,characterData:true});
              window.turnObserver=new MutationObserver(records=>turnMutations+=records.length);
              turnObserver.observe(document.getElementById('turnCount'),{childList:true,subtree:true});
              return true;
            })()""")
            for _ in range(2):
                for name in direction:
                    snapshot = await invoke('move', [name])
            assert snapshot['turn'] == 4
            assert view.evaluate('stableMutations.length') == 0, view.evaluate('JSON.stringify(stableMutations)')
            assert view.evaluate('turnMutations') > 0
            assert view.evaluate("logNodes.every((node,index)=>node===document.querySelectorAll('#logLines p')[index])")
            assert view.evaluate("canvasNode===document.getElementById('board')")
            view.evaluate('htmlObserver.disconnect();turnObserver.disconnect()')

            # Real asynchronous disk save: feedback appears only after the delay,
            # while the Python command gate rejects duplicates from the first instant.
            original_save = store.save
            save_gate = asyncio.Event()

            async def slow_save(payload):
                await save_gate.wait()
                await original_save(payload)

            store.save = slow_save
            before_turn = controller.game.state['turn']
            view.evaluate("window.pendingSave=EmberUI.invoke('save_game');true")
            assert not view.evaluate("document.getElementById('languageEn').disabled")
            await invoke('move', ['right'])
            assert controller.game.state['turn'] == before_turn
            await view.wait_until(lambda: view.evaluate("document.getElementById('app').classList.contains('busy')"), timeout=5)
            assert view.evaluate("document.getElementById('languageEn').disabled")
            assert view.evaluate("document.getElementById('saveStatus').textContent") == 'Saving embers…'
            save_gate.set()
            await view.evaluate_async('pendingSave')
            assert not view.evaluate("document.getElementById('app').classList.contains('busy')")
            assert not view.evaluate("document.getElementById('languageEn').disabled")
            assert view.evaluate("document.getElementById('saveStatus').textContent") == 'Saved'

            async def fail_save(payload):
                raise OSError('test disk unavailable')

            store.save = fail_save
            await invoke('save_game')
            assert view.evaluate("document.getElementById('saveStatus').classList.contains('bad')")
            assert view.evaluate("document.getElementById('saveStatus').textContent") == 'Not saved'
            assert 'test disk unavailable' in view.evaluate("document.getElementById('errorText').textContent")
            store.save = original_save
            await invoke('save_game')
            assert not view.evaluate("document.getElementById('saveStatus').classList.contains('bad')")

            before = controller.game.export()
            await invoke('set_language', ['zh-CN'])
            assert controller.game.export() == before
            assert view.evaluate("document.getElementById('floorName').textContent").startswith('第 1 层')
            assert view.evaluate("document.getElementById('saveStatus').textContent") == '灯火已存'
            await invoke('set_paused', [True])
            view.evaluate("document.getElementById('pauseGuideBtn').click()")
            await view.wait_until(lambda: view.evaluate("!!document.getElementById('closeGuideBtn')"), timeout=5)
            await invoke('set_language', ['en'])
            assert view.evaluate("!!document.getElementById('closeGuideBtn')")
            assert 'Traveller’s guide' in view.evaluate("document.getElementById('card').textContent")
            assert view.evaluate("document.getElementById('inspect').textContent").startswith('WASD move')
            view.evaluate("document.getElementById('closeGuideBtn').click()")
            await view.wait_until(lambda: view.evaluate("!!document.getElementById('resumeBtn')"), timeout=5)
            await invoke('set_paused', [False])
            assert view.evaluate("document.getElementById('overlay').classList.contains('hidden')")
            assert view.evaluate('EmberUI.diagnostics().error') == ''
            from ultralight_py.images import to_pillow
            capture = ROOT / 'build' / 'native-html.png'
            capture.parent.mkdir(parents=True, exist_ok=True)
            await asyncio.sleep(.25)
            to_pillow(view.copy_pixels()).save(capture)
            print('NATIVE HTML PASS: four moves, zero unchanged-DOM mutations, stable log/Canvas, delayed feedback, duplicate gate, save errors, language/menu/help')
        finally:
            app.close()
            await task
            api.close()


if __name__ == '__main__':
    asyncio.run(main())
