"""Emberkeep — a native ultralight-py 0.5.0 pixel roguelike."""
import argparse
import asyncio
from importlib.metadata import version
import json
import mimetypes
from pathlib import Path
import sys
import tempfile
import traceback

from game.bridge import Controller
from game.storage import SaveStore

ROOT = Path(__file__).resolve().parent


def create_application(controller, cpu=False, cache_path=None, width=1280, height=800):
    from ultralight_py import API, Application, Resource
    if version('ultralight-py') != '0.5.0':
        raise RuntimeError('Requires ultralight-py==0.5.0. Reinstall requirements.txt.')
    resources = {}
    types = {'.js': 'text/javascript', '.woff2': 'font/woff2', '.png': 'image/png'}
    for path in (ROOT / 'assets').rglob('*'):
        if path.is_file():
            mime = types.get(path.suffix) or mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
            resources[path.relative_to(ROOT / 'assets').as_posix()] = Resource(path.read_bytes(), mime)
    api = API('host')
    try:
        app = Application(assets_root=ROOT / 'assets', resource_loader=resources.get,
                          cache_path=cache_path, force_cpu_renderer=cpu,
                          app_name='Emberkeep', developer_name='Emberkeep')
        # Game API registration lives in game.bridge.Controller.register_api().
        controller.register_api(api)
        window = app.create_window(width, height, title='Emberkeep / 烬灯地牢')

        @api.register
        async def quit_game():
            if controller.game.state and controller.game.state['phase'] in ('playing', 'upgrade'):
                await controller.save_game()
            asyncio.get_running_loop().call_later(.08, window.close)

        api.attach(window.view)
        window.view.on('console', lambda message: print('[web]', message, file=sys.stderr)
                       if message.get('level') in ('error', 3) else None)
        window.view.load_url('file:///index.html')
        return app, window, api
    except BaseException:
        api.close()
        raise


async def smoke(controller, cpu, folder):
    app, window, api = create_application(controller, cpu, Path(folder) / 'cache')
    task = asyncio.create_task(app.run_async())
    try:
        await window.view.wait_ready(timeout=20)
        await window.view.wait_until(lambda: window.view.evaluate('!!window.EMBER_READY'), timeout=20)
        result = await window.view.evaluate_async('window.EmberUI.invoke("new_run", [314159])')
        assert result['phase'] == 'playing' and result['player']['hp'] == 42
        assert window.view.evaluate('typeof host.move') == 'function'
        assert window.view.evaluate('typeof host.game.whirl') == 'function'
        result = await window.view.evaluate_async('window.EmberUI.invoke("game.wait_turn")')
        assert result['turn'] == 1 and window.view.evaluate('host.game.turn') == 1
        assert window.view.evaluate('host.game.hero.hp') == result['player']['hp']
        assert window.view.evaluate('(function(){try{host.game.hero.hp=999;return false;}catch(e){return true;}})()')
        await window.view.evaluate_async('window.EmberUI.invoke("save_game")')
        result = await window.view.evaluate_async('window.EmberUI.invoke("load_game")')
        assert result['turn'] == 1
        assert window.view.evaluate('window.EmberUI.diagnostics().error') == ''
        print('SMOKE PASS: 0.5.0 AppCore, pixel assets, typed API, live read-only proxy, async save/load')
    finally:
        app.close()
        await task
        api.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lang', choices=('en', 'zh-CN'), help='Initial UI language (overrides remembered preference)')
    parser.add_argument('--cpu', action='store_true', help='Use CPU rendering (also supports pixel capture)')
    parser.add_argument('--seed', type=int, help='Fixed starting seed, 0..2147483647')
    parser.add_argument('--data-dir', type=Path, help='Save directory; default ~/.emberkeep')
    parser.add_argument('--smoke', action='store_true', help='Native self-test with an isolated temporary save')
    parser.add_argument('--smoke-report', type=Path, help='Write a JSON result (requires --smoke)')
    args = parser.parse_args()
    if args.smoke_report and not args.smoke:
        parser.error('--smoke-report requires --smoke')
    if args.seed is not None and not 0 <= args.seed < 2**31:
        parser.error('--seed must be between 0 and 2147483647')
    if args.smoke:
        report = {'passed': False, 'language': args.lang, 'error': None}
        try:
            with tempfile.TemporaryDirectory(prefix='emberkeep-smoke-') as folder:
                controller = Controller(SaveStore(folder), args.seed, args.lang)
                asyncio.run(smoke(controller, args.cpu, folder))
            report['passed'] = True
        except Exception as exc:
            report['error'] = f'{type(exc).__name__}: {exc}'
            traceback.print_exc()
        finally:
            if args.smoke_report:
                args.smoke_report.parent.mkdir(parents=True, exist_ok=True)
                args.smoke_report.write_text(json.dumps(report, indent=2), encoding='utf-8')
        if not report['passed']:
            raise SystemExit(1)
    else:
        store = SaveStore(args.data_dir)
        controller = Controller(store, args.seed, args.lang)
        app, _, api = create_application(controller, args.cpu, store.directory / 'cache')
        try:
            app.run()
        finally:
            app.close()
            api.close()


if __name__ == '__main__':
    try:
        main()
    except ImportError as exc:
        raise SystemExit(f'Missing dependency: {exc}\nRun python -m pip install -r requirements.txt') from exc
