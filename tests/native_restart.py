"""Prove Continue restores a run across two fresh native application processes."""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from game.bridge import Controller
from game.engine import Game
from game.i18n import localize_snapshot
from game.storage import SaveStore
from run import create_application
from tests.player_bot import choose_action


def digest(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def stable(snapshot):
    return {k: v for k, v in snapshot.items() if k not in ('revision', 'events', 'has_save', 'saved', 'save_error')}


async def worker(mode, folder):
    controller = Controller(SaveStore(folder), language='en')
    app, window, api = create_application(controller, True, folder/'cache')
    task = asyncio.create_task(app.run_async())
    try:
        await window.view.wait_ready(timeout=20)
        await window.view.wait_until(lambda: window.view.evaluate('!!window.EMBER_READY'), timeout=20)
        expected_path = folder/'expected.json'
        if mode == 'write':
            s = await window.view.evaluate_async('window.EmberUI.invoke("new_run",[19])')
            visits = {}
            for _ in range(60):
                k = s['floor'], s['player']['x'], s['player']['y']
                visits[k] = visits.get(k, 0)+1
                method, args = choose_action(s, visits)
                s = await window.view.evaluate_async(f'window.EmberUI.invoke({json.dumps(method)},{json.dumps(args)})')
            while s['phase'] == 'upgrade':
                method, args = choose_action(s, visits)
                s = await window.view.evaluate_async(f'window.EmberUI.invoke({json.dumps(method)},{json.dumps(args)})')
            await window.view.evaluate_async('window.EmberUI.invoke("save_game")')
            payload = await controller.store.load()
            reference = Game()
            reference.restore(payload)
            expected = {'digest': digest(payload), 'loaded': stable(s),
                        'next_turn': stable(localize_snapshot(reference.wait_turn(), 'en'))}
            expected_path.write_text(json.dumps(expected, ensure_ascii=False), encoding='utf-8')
            print('NATIVE RESTART write', s['turn'], s['kills'], flush=True)
        else:
            expected = json.loads(expected_path.read_text(encoding='utf-8'))
            assert not window.view.evaluate('document.getElementById("continueBtn").disabled')
            await window.view.evaluate_async('document.getElementById("continueBtn").click()')
            await window.view.wait_until(lambda: window.view.evaluate(
                'window.EmberUI.diagnostics().phase!=="menu" && !window.EmberUI.diagnostics().busy'), timeout=15)
            s = window.view.evaluate('window.EmberUI.snapshot()')
            assert stable(s) == expected['loaded']
            assert digest(controller.game.export()) == expected['digest']
            next_ = await window.view.evaluate_async('window.EmberUI.invoke("game.wait_turn")')
            assert stable(next_) == expected['next_turn']
            assert not window.view.evaluate('window.EmberUI.diagnostics().error')
            (folder/'restart-result.json').write_text(json.dumps({'passed': True,
                'fresh_processes': 2, 'restored_turn': s['turn'], 'restored_kills': s['kills'],
                'state_and_rng_sha256': expected['digest'], 'next_turn_matches': True}, indent=2))
            print('NATIVE RESTART PASS', s['turn'], flush=True)
    finally:
        app.close()
        await task
        api.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', choices=['write', 'read'])
    parser.add_argument('--data-dir', type=Path)
    parser.add_argument('--output', type=Path, default=ROOT/'docs'/'reports'/'native-restart.json')
    args = parser.parse_args()
    if args.worker:
        asyncio.run(worker(args.worker, args.data_dir))
    else:
        with tempfile.TemporaryDirectory(prefix='emberkeep-restart-') as directory:
            for mode in ['write', 'read']:
                subprocess.run([sys.executable, str(Path(__file__).resolve()), '--worker', mode,
                                '--data-dir', directory], check=True, cwd=ROOT)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text((Path(directory)/'restart-result.json').read_text())
