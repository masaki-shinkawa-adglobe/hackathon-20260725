"""Planner output is untrusted JSON; this module never executes it."""
from typing import Any
from .plan_schema import deterministic_plan, validate_plan

def accept_plan(output: Any, candidates: set[int], max_parallel: int) -> dict[str, Any]:
    return validate_plan(output, candidates, max_parallel)

__all__ = ["accept_plan", "deterministic_plan"]
