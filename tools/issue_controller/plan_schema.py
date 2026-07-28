from __future__ import annotations
from collections import defaultdict
from typing import Any
from .validation import issue_number

def validate_plan(value: Any, candidates: set[int], max_parallel: int) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) - {"schema_version","batches","dependencies","clarifications","warnings"}: raise ValueError("invalid plan keys")
    if value.get("schema_version") != 1 or not isinstance(value.get("batches"), list): raise ValueError("invalid plan schema")
    seen:set[int]=set(); edges:dict[int,set[int]]=defaultdict(set)
    for batch in value["batches"]:
        if not isinstance(batch, dict) or set(batch) != {"issues","reason"} or not isinstance(batch["reason"],str) or not isinstance(batch["issues"],list) or not 1 <= len(batch["issues"]) <= max_parallel: raise ValueError("invalid batch")
        for n in batch["issues"]:
            n=issue_number(n)
            if n not in candidates or n in seen: raise ValueError("unknown or duplicate issue")
            seen.add(n)
    if seen != candidates: raise ValueError("plan must include each candidate exactly once")
    for dep in value.get("dependencies",[]):
        if not isinstance(dep,dict) or set(dep)!={"before","after","reason"} or not isinstance(dep["reason"],str): raise ValueError("invalid dependency")
        before,after=issue_number(dep["before"]),issue_number(dep["after"])
        if before not in candidates or after not in candidates or before==after: raise ValueError("invalid dependency issue")
        edges[before].add(after)
    def visit(n:int, active:set[int], done:set[int]) -> None:
        if n in active: raise ValueError("cyclic dependency")
        if n in done:return
        active.add(n)
        for x in edges[n]:visit(x,active,done)
        active.remove(n);done.add(n)
    done=set()
    for n in candidates: visit(n,set(),done)
    clarifications=value.get("clarifications", [])
    per_issue=set()
    for c in clarifications:
        if not isinstance(c,dict) or set(c)!={"issue","question","why_blocking","options"}: raise ValueError("invalid clarification")
        n=issue_number(c["issue"])
        if n not in candidates or n in per_issue or not all(isinstance(c[k],str) and c[k].strip() for k in ("question","why_blocking")) or not isinstance(c["options"],list) or not 1 <= len(c["options"]) <= 2 or not all(isinstance(x,str) and x.strip() for x in c["options"]): raise ValueError("invalid clarification")
        per_issue.add(n)
    if not isinstance(value.get("warnings",[]),list) or not all(isinstance(x,str) for x in value.get("warnings",[])): raise ValueError("invalid warnings")
    return value

def deterministic_plan(candidates: list[int], max_parallel: int) -> dict[str, Any]:
    ordered=sorted(issue_number(x) for x in candidates)
    return {"schema_version":1,"batches":[{"issues":ordered[i:i+max_parallel],"reason":"deterministic fallback"} for i in range(0,len(ordered),max_parallel)],"dependencies":[],"clarifications":[],"warnings":["planner fallback used"]}
