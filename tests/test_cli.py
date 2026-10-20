from typer.testing import CliRunner

from ticketpilot.cli import app

runner = CliRunner()


def test_help_lists_command_groups():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for name in ("data", "triage", "kb", "serve", "helpdesk"):
        assert name in result.output


def test_data_generate_writes_jsonl(tmp_path):
    target = tmp_path / "out.jsonl"
    result = runner.invoke(app, ["data", "generate", "--count", "25", "--output", str(target)])
    assert result.exit_code == 0
    assert len(target.read_text(encoding="utf-8").splitlines()) == 25


def test_unknown_training_task_is_rejected():
    result = runner.invoke(app, ["triage", "train", "--task", "nope"])
    assert result.exit_code != 0
