"""Real AppCore language switching, focus, persistence and both-language layouts."""
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
    from ultralight_py.images import to_pillow
    with tempfile.TemporaryDirectory(prefix='emberkeep-i18n-') as directory:
        controller = Controller(SaveStore(directory), language='en')
        app, window, api = create_application(controller, True, Path(directory)/'cache')
        task = asyncio.create_task(app.run_async())
        view = window.view
        async def ready(v):
            await v.wait_ready(timeout=20)
            await v.wait_until(lambda: v.evaluate('!!window.EMBER_READY'), timeout=20)
        async def switch(language):
            previous = view.evaluate('EmberUI.diagnostics().calls')
            button = 'languageEn' if language == 'en' else 'languageZh'
            # Actual AppCore mouse input, not a synthetic change event.
            position = view.evaluate(f"(function(){{const r=document.getElementById('{button}').getBoundingClientRect();return [r.left+r.width/2,r.top+r.height/2]}})()")
            view.focus()
            view.click(round(position[0]), round(position[1]))
            await view.wait_until(lambda: view.evaluate(f'EmberUI.diagnostics().calls>{previous}&&!EmberUI.diagnostics().busy'), timeout=10)
            assert view.evaluate('document.documentElement.lang') == language
        try:
            await ready(view)
            view.evaluate("document.getElementById('seedInput').value='19';document.getElementById('seedInput').focus()")
            await switch('zh-CN')
            assert view.evaluate("document.getElementById('seedInput').value") == '19'
            assert view.evaluate('document.activeElement.id') == 'seedInput'
            assert view.evaluate("document.getElementById('startBtn').textContent").startswith('点燃')
            await switch('en')
            assert 'Light the lantern' in view.evaluate("document.getElementById('startBtn').textContent")
            await view.evaluate_async('EmberUI.invoke("new_run",[19])')
            before = controller.game.export()
            await switch('zh-CN')
            assert controller.game.export() == before
            assert view.evaluate("document.getElementById('floorName').textContent").startswith('第 1 层')
            await switch('en')
            assert controller.game.export() == before
            assert view.evaluate("document.getElementById('floorName').textContent").startswith('Floor 1')
            await asyncio.sleep(.25)
            to_pillow(view.copy_pixels()).save(ROOT/'docs/screenshots/gameplay-en.png')
            await view.evaluate_async('EmberUI.invoke("set_paused",[true])')
            view.evaluate("document.getElementById('pauseGuideBtn').click()")
            await view.wait_until(lambda: view.evaluate("!!document.getElementById('closeGuideBtn')"), timeout=10)
            await switch('zh-CN')
            assert view.evaluate("document.getElementById('card').textContent").startswith('THE WAY OF THE LANTERN旅人手册')
            assert controller.game.state['paused']
            view.evaluate("document.getElementById('closeGuideBtn').click()")
            assert view.evaluate("!!document.getElementById('resumeBtn')")
            await view.evaluate_async('EmberUI.invoke("boot")')
            await switch('en')
            assert view.evaluate('EmberUI.snapshot().phase') == 'menu'
            assert controller.game.state['paused']
            assert view.evaluate("localStorage.getItem('emberkeep.language')") == 'en'
            assert view.evaluate('EmberUI.diagnostics().error') == ''
            # A new view uses the remembered preference, even if browser locale differs.
            controller.language_override = False
            controller.language = 'zh-CN'
            for width,height in [(800,600),(1600,1000)]:
                other = app.create_window(width,height,title='Emberkeep i18n layout')
                api.attach(other.view)
                other.view.load_url('file:///index.html')
                await ready(other.view)
                assert other.view.evaluate('document.documentElement.lang') == 'en'
                for language in ('en','zh-CN'):
                    await other.view.evaluate_async(f'EmberUI.invoke("set_language",[{json.dumps(language)}])')
                    assert not other.view.evaluate('EmberUI.diagnostics().error')
                    assert other.view.evaluate("document.getElementById('app').scrollWidth<=innerWidth")
                    await asyncio.sleep(.15)
                    to_pillow(other.view.copy_pixels()).save(ROOT/f'docs/reports/i18n-{width}-{language}.png')
                other.close()
            print('NATIVE I18N PASS: menu, HUD, help, pause, focus, remembered preference, 800/1280/1600 layouts')
        finally:
            app.close()
            await task
            api.close()


if __name__ == '__main__':
    (ROOT/'docs/reports').mkdir(parents=True,exist_ok=True)
    asyncio.run(main())
