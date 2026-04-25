from __future__ import annotations


def test_cli_imports():
    from codepilot.cli.main import app

    assert app is not None


def test_server_imports():
    from codepilot.server.main import app

    assert app.title == "CodePilot Agent Server"


def test_server_frontend_files_exist():
    from codepilot.server.main import STATIC_DIR

    assert (STATIC_DIR / "index.html").exists()
    assert (STATIC_DIR / "app.js").exists()
    assert (STATIC_DIR / "styles.css").exists()
    assert (STATIC_DIR / "logo.png").exists()
