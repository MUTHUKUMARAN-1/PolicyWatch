import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import pytest  # noqa: E402

from ptct.config import load_config  # noqa: E402
from ptct.storage import Storage  # noqa: E402


@pytest.fixture
def settings():
    return load_config(ROOT / "config" / "sources.yaml")


@pytest.fixture
def storage(tmp_path):
    s = Storage(tmp_path / "t.db", tmp_path / "snaps")
    yield s
    s.close()


@pytest.fixture
def fx():
    def _read(name):
        return (ROOT / "fixtures" / name).read_text(encoding="utf-8")
    return _read
