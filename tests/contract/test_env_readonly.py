import os

from rocket.config import env


def test_env_read_does_not_delete_or_rename(monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", "present-in-environment")
    assert env("FRED_API_KEY") == "present-in-environment"
    assert os.environ["FRED_API_KEY"] == "present-in-environment"


def test_nave_alias_is_accepted(monkeypatch):
    monkeypatch.delenv("ROCKET_HOME", raising=False)
    monkeypatch.setenv("NAVE_RESEARCH_STATE_DIR", "/tmp/rocket-alias-test")
    assert env("ROCKET_HOME") == "/tmp/rocket-alias-test"
    assert os.environ["NAVE_RESEARCH_STATE_DIR"] == "/tmp/rocket-alias-test"
