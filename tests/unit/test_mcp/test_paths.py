"""Tests for shared runtime path helpers."""

from pathlib import Path

from benedict.paths import find_repo_root, get_data_dir, get_env_file


def test_get_data_dir_uses_env(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("BENEDICT_DATA_DIR", str(tmp_path))
    assert get_data_dir() == tmp_path.resolve()


def test_get_env_file_uses_env(tmp_path: Path, monkeypatch):
    env_file = tmp_path / "custom.env"
    monkeypatch.setenv("BENEDICT_ENV_FILE", str(env_file))
    assert get_env_file() == env_file.resolve()


def test_find_repo_root_finds_pyproject():
    root = find_repo_root()
    assert (root / "pyproject.toml").exists()
