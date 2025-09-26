from typer.testing import CliRunner

from .cli import app

runner = CliRunner()


def test_app():
    result = runner.invoke(app)
    assert result.exit_code == 0
    assert result.output == "hello, world\n"
