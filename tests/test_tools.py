from __future__ import annotations

import pytest

from codepilot.tools.filesystem import read_file, write_file
from codepilot.tools.shell import run_command


def test_filesystem_blocks_path_escape(tmp_path):
    with pytest.raises(ValueError):
        read_file(tmp_path, "../secret.txt")


def test_write_and_read_file(tmp_path):
    write_file(tmp_path, "src/demo.txt", "hello")
    assert read_file(tmp_path, "src/demo.txt") == "hello"


def test_shell_allows_python_version(tmp_path):
    result = run_command(tmp_path, "python --version")
    assert result["exit_code"] == 0
