from pathlib import Path

import pytest


@pytest.fixture
def data_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point every path helper at an empty temp dir for the duration of a test."""
    monkeypatch.setenv("VADIBOOK_DATA", str(tmp_path))
    return tmp_path
