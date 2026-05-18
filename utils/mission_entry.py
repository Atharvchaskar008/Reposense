"""Jac entry hook — delegates to production orchestrator."""

from orchestrator import run_analysis as execute_mission

__all__ = ["execute_mission"]
