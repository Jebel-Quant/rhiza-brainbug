"""License compliance — pip-licenses, failing on copyleft (needs the environment)."""

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import LICENSE_FAIL_ON, report, uv_tool


@pytest.mark.requires_env
def test_license_compliance(upstream: Path, env_ready: bool) -> None:
    """No GPL/LGPL/AGPL dependencies (matches rhiza's `make license`)."""
    proc = uv_tool(upstream, "pip-licenses",
                   ["pip-licenses", f"--fail-on={LICENSE_FAIL_ON}"])
    assert proc.returncode == 0, report("pip-licenses", proc)
