import re
from pathlib import Path

import zoomms


def test_version_single_source():
    toml = (Path(__file__).parent.parent / "pyproject.toml").read_text()
    assert 'dynamic = ["version"]' in toml and "zoomms.__version__" in toml
    assert re.fullmatch(r"\d+\.\d+\.\d+", zoomms.__version__)
