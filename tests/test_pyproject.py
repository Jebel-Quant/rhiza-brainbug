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


def test_python_version_declared(pyproject: dict) -> None:
    """Declares its Python version coverage.

    Either via `Programming Language :: Python :: 3.x` classifiers OR a
    `requires-python` constraint — both are valid ways to declare supported
    versions, so accept either (many modern projects use requires-python only).
    """
    project = pyproject.get("project", {})
    classifiers = project.get("classifiers", [])
    has_classifiers = any(
        c.startswith("Programming Language :: Python :: 3.") for c in classifiers
    )
    has_requires_python = bool(project.get("requires-python"))
    assert has_classifiers or has_requires_python, (
        "no Python version declared (need Python 3.x classifiers or requires-python)"
    )
