"""The uv workspace members that ship beside the framework.

``WORKSPACE_MEMBERS`` maps each member's directory under ``packages/`` to its
distribution name, in the root workspace's declared order. The two differ for
``dock-engine`` (distribution ``osprey-dock-engine``), so paths and
``#subdirectory=`` fragments use the key and requirement names, wheel names and
``Requires-Dist`` matching use the value. The deployment plumbing reads this
constant rather than the monorepo's root ``pyproject.toml``, so an installed
framework that has no checkout beside it still knows which member wheels it
needs. A test pins it equal to the root ``[tool.uv.workspace].members``.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

WORKSPACE_MEMBERS: Mapping[str, str] = MappingProxyType(
    {
        "osprey-connectors": "osprey-connectors",
        "pyaml-cs-osprey": "pyaml-cs-osprey",
        "dock-engine": "osprey-dock-engine",
    }
)


def member_requirements(spec: str) -> list[str]:
    """One direct-reference requirement per member, rooted at the VCS URL *spec*.

    *spec* is the framework's URL without a fragment (a ``git+`` URL, or a
    placeholder such as ``${OSPREY_PIP_SPEC}`` a Dockerfile expands). Each line
    reads ``<distribution> @ <spec>#subdirectory=packages/<directory>``.
    """
    return [
        f"{dist} @ {spec}#subdirectory=packages/{directory}"
        for directory, dist in WORKSPACE_MEMBERS.items()
    ]
