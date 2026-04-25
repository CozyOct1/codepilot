from __future__ import annotations


def test_cli_imports():
    from codepilot.cli.main import app

    assert app is not None


def test_server_imports():
    from codepilot.server.main import app

    assert app.title == "CodePilot Agent Server"
