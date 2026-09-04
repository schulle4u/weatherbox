import json
import signal
from pathlib import Path
from unittest.mock import Mock

import pytest

from weatherbox import cli
from weatherbox.config import load_config
from conftest import write_test_config


@pytest.mark.parametrize("interval", ["0", "-1", "1.5", "nan"])
def test_serve_rejects_invalid_interval(interval):
    with pytest.raises(SystemExit) as exc:
        cli.build_parser().parse_args(["serve", "--interval-seconds", interval])
    assert exc.value.code == 2


def test_serve_retries_after_failed_pass_and_stops_during_wait(monkeypatch, capsys):
    stop = Mock()
    stop.is_set.return_value = False
    stop.wait.side_effect = [False, True]
    monkeypatch.setattr(cli.threading, "Event", lambda: stop)
    monkeypatch.setattr(cli.signal, "signal", Mock(return_value=signal.SIG_DFL))
    service = Mock()
    service.run_due.side_effect = [{"first": "ERROR: temporary outage"}, {"first": "audio.mp3"}]

    assert cli._serve(service, 15) == 0
    assert service.run_due.call_count == 2
    assert [call.args for call in stop.wait.call_args_list] == [(15,), (15,)]
    assert [json.loads(line) for line in capsys.readouterr().out.splitlines()] == [
        {"first": "ERROR: temporary outage"}, {"first": "audio.mp3"},
    ]


@pytest.mark.parametrize("stop_signal", [signal.SIGTERM, signal.SIGINT])
def test_serve_finishes_active_pass_on_signal_and_restores_handlers(monkeypatch, stop_signal):
    handlers = {}
    original = object()

    def install(sig, handler):
        previous = handlers.get(sig, original)
        handlers[sig] = handler
        return previous

    monkeypatch.setattr(cli.signal, "signal", install)
    completed = []

    def run_due():
        handlers[stop_signal](stop_signal, None)
        completed.append(True)
        return {}

    service = Mock(run_due=Mock(side_effect=run_due))
    assert cli._serve(service, 3600) == 0
    assert completed == [True]
    assert service.run_due.call_count == 1
    assert handlers == {signal.SIGTERM: original, signal.SIGINT: original}


def test_serve_restores_handlers_on_unexpected_error(monkeypatch):
    install = Mock(return_value=signal.SIG_DFL)
    monkeypatch.setattr(cli.signal, "signal", install)
    service = Mock()
    service.run_due.side_effect = RuntimeError("broken state")
    with pytest.raises(RuntimeError, match="broken state"):
        cli._serve(service, 60)
    assert [call.args for call in install.call_args_list[-2:]] == [
        (signal.SIGTERM, signal.SIG_DFL), (signal.SIGINT, signal.SIG_DFL),
    ]


def test_cli_dispatches_serve_with_config_and_interval(monkeypatch, tmp_path):
    config = write_test_config(tmp_path / "config.yaml")
    service = Mock()
    factory = Mock(return_value=service)
    serve = Mock(return_value=0)
    monkeypatch.setattr(cli, "WeatherboxService", factory)
    monkeypatch.setattr(cli, "_serve", serve)
    assert cli.main(["--config", str(config), "serve", "--interval-seconds", "5"]) == 0
    serve.assert_called_once_with(service, 5)
    assert factory.call_args.args[0].source_path == config.resolve()


def test_docker_example_loads_without_external_models_or_audio():
    config = load_config(Path(__file__).parents[1] / "deploy/docker/config.example.yaml")
    assert config.tts.provider == "gtts"
    assert config.tts.fallback_provider == "espeak-ng"
    for location in config.enabled_locations:
        for assets in location.jingles.values():
            assert assets.intro is None
            assert assets.outro is None
            assert assets.music is None
