from pathlib import Path

import pytest

from weather_agent import config


def test_load_env_reads_key_value_pairs_and_ignores_comments(tmp_path: Path):
    env = tmp_path / ".env"
    env.write_text("# comment\nMISTRAL_API_KEY=abc\n\nANTHROPIC_API_KEY = 'xyz'\n")
    assert config.load_env(env) == {"MISTRAL_API_KEY": "abc", "ANTHROPIC_API_KEY": "xyz"}


def test_load_env_missing_file_returns_empty(tmp_path: Path):
    assert config.load_env(tmp_path / "nope") == {}


def test_update_settings_rejects_unknown_handler():
    with pytest.raises(ValueError):
        config.update_settings({"understand": "not-a-model"})


def test_update_settings_changes_one_field_only():
    before = config.current_settings()
    after = config.update_settings({"offline": True})
    assert after.offline is True and after.understand == before.understand
    config.update_settings({"offline": False})
