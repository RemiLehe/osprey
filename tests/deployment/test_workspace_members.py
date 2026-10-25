"""WORKSPACE_MEMBERS stays in step with the root uv workspace."""

from __future__ import annotations

import tomllib
from pathlib import Path

from osprey.deployment.members import WORKSPACE_MEMBERS, member_requirements

_ROOT = Path(__file__).resolve().parents[2]


def _declared_members() -> list[str]:
    pyproject = tomllib.loads((_ROOT / "pyproject.toml").read_text())
    return pyproject["tool"]["uv"]["workspace"]["members"]


def test_members_match_the_root_workspace() -> None:
    """Every declared member directory is a key, in the declared order, and nothing else."""
    assert list(WORKSPACE_MEMBERS) == [Path(m).name for m in _declared_members()]


def test_every_member_value_is_its_distribution_name() -> None:
    """The value is the ``project.name`` the member directory's pyproject declares."""
    for directory, dist in WORKSPACE_MEMBERS.items():
        member_pyproject = tomllib.loads(
            (_ROOT / "packages" / directory / "pyproject.toml").read_text()
        )
        assert member_pyproject["project"]["name"] == dist


def test_dock_engine_directory_differs_from_its_distribution() -> None:
    """The one member whose directory is not its distribution name."""
    assert WORKSPACE_MEMBERS["dock-engine"] == "osprey-dock-engine"


def test_member_requirements_name_the_dist_and_point_at_the_directory() -> None:
    """One line per member, in order: ``<dist> @ <spec>#subdirectory=packages/<dir>``."""
    spec = "git+https://example.invalid/osprey.git@main"
    assert member_requirements(spec) == [
        f"osprey-connectors @ {spec}#subdirectory=packages/osprey-connectors",
        f"pyaml-cs-osprey @ {spec}#subdirectory=packages/pyaml-cs-osprey",
        f"osprey-dock-engine @ {spec}#subdirectory=packages/dock-engine",
    ]
