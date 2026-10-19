"""Execution subsystem — channel write safety limits.

Provides :class:`LimitsValidator` for enforcing configured min/max/step
constraints on control system channel writes.

Note: LimitsValidator canonical location is osprey_connectors.control_system._limits_validator.
"""

from osprey_connectors.control_system import LimitsValidator

__all__ = ["LimitsValidator"]
