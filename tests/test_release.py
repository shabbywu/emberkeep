"""Release gates must reject wrong tags and report failures without a GUI dialog."""
import json
import sys

import pytest

import run
from tools import build_release


def test_tag_must_match_project_version():
    version = build_release.release_version()
    assert build_release.release_version(f'v{version}') == version
    with pytest.raises(ValueError, match='Release tag must be'):
        build_release.release_version('v999.0.0')
    assert build_release.release_version(build_id='a' * 40) == f'{version}-aaaaaaa'
    with pytest.raises(ValueError, match='Build ID'):
        build_release.release_version(build_id='../bad')


@pytest.mark.parametrize('fails', [False, True])
def test_smoke_report_records_result_and_exit_code(monkeypatch, tmp_path, fails):
    report = tmp_path / 'nested' / 'result.json'
    monkeypatch.setattr(sys, 'argv', ['run.py', '--smoke', '--lang', 'zh-CN',
                                     '--smoke-report', str(report)])
    monkeypatch.setattr(run, 'Controller', lambda *args: object())

    async def smoke(*args):
        if fails:
            raise RuntimeError('native startup failed')

    monkeypatch.setattr(run, 'smoke', smoke)
    if fails:
        with pytest.raises(SystemExit) as exited:
            run.main()
        assert exited.value.code == 1
    else:
        run.main()
    result = json.loads(report.read_text(encoding='utf-8'))
    assert result['passed'] is not fails
    assert result['language'] == 'zh-CN'
    assert result['error'] == ('RuntimeError: native startup failed' if fails else None)


def test_report_requires_smoke(monkeypatch, tmp_path):
    report = tmp_path / 'result.json'
    monkeypatch.setattr(sys, 'argv', ['run.py', '--smoke-report', str(report)])
    with pytest.raises(SystemExit) as exited:
        run.main()
    assert exited.value.code == 2
    assert not report.exists()
