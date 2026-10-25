"""The dock layout rules shared by OSPREY and CANOPY.

The Python side of `@als-apg/dock-engine`: the layout rules themselves
(:mod:`dock_engine.layout`), the case corpus the engine is held to and the digest
of its layout rules. Standard library only, and independent of the framework.
"""

from ._data import cases_dir, rules_digest
from .layout import (
    LAYOUT_REASONS,
    REASON_TEXT,
    SIZE_TOLERANCE,
    SPLITS,
    LayoutForm,
    LayoutRefused,
    layout_keys,
    layout_refusal,
    normalize_layout,
    old_shape_refusal,
    validate_layout,
)

# The version comes from the framework's v-tags (see pyproject.toml): a built
# distribution answers from its own metadata, and a bare source tree — no dist
# installed, no build hook run — answers honestly that it is unbuilt.
try:
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as _dist_version

    __version__ = _dist_version("osprey-dock-engine")
except PackageNotFoundError:  # pragma: no cover — source tree without an install
    __version__ = "0.0.0+unbuilt"

__all__ = [
    "LAYOUT_REASONS",
    "REASON_TEXT",
    "SIZE_TOLERANCE",
    "SPLITS",
    "LayoutForm",
    "LayoutRefused",
    "__version__",
    "cases_dir",
    "layout_keys",
    "layout_refusal",
    "normalize_layout",
    "old_shape_refusal",
    "rules_digest",
    "validate_layout",
]
