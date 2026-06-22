"""Structure check — validate the upstream's pyproject.toml (pure file inspection)."""

from __future__ import annotations


def test_has_pyproject(pyproject: dict) -> None:
    """pyproject.toml exists and parses (fixture skips if absent)."""
    assert isinstance(pyproject, dict)


def test_project_metadata(pyproject: dict) -> None:
    """[project] declares name, version (or dynamic), and requires-python."""
    project = pyproject.get("project")
    assert project, "missing [project] table"
    assert project.get("name"), "[project].name is required"
    dynamic = project.get("dynamic", [])
    assert project.get("version") or "version" in dynamic, \
        "[project].version must be set or declared dynamic"
    assert project.get("requires-python"), "[project].requires-python is required"


def test_python_classifiers(pyproject: dict) -> None:
    """Declares at least one `Programming Language :: Python :: 3.x` classifier.

    rhiza's CI derives its Python test matrix from these; a repo without them
    has no declared version coverage.
    """
    classifiers = pyproject.get("project", {}).get("classifiers", [])
    py = [c for c in classifiers if c.startswith("Programming Language :: Python :: 3.")]
    assert py, "no `Programming Language :: Python :: 3.x` classifiers declared"
