from __future__ import annotations
from .models import IssueState, Phase
def schedulable(issues:list[IssueState], dependencies:dict[int,set[int]], maximum:int)->list[IssueState]:
    active={Phase.PREPARING,Phase.RUNNING,Phase.VALIDATING,Phase.REVIEWING}
    out=[]
    for issue in issues:
        if issue.phase is not Phase.DISCOVERED or len(out)+sum(x.phase in active for x in issues)>=maximum: continue
        if all(next((x.phase for x in issues if x.issue_number==before),Phase.BLOCKED) is Phase.DONE for before in dependencies.get(issue.issue_number,set())): out.append(issue)
    return out
def path_conflicts(candidate:int, paths:set[str], states:list[IssueState])->bool:
    return any(s.issue_number!=candidate and s.phase in {Phase.RUNNING,Phase.VALIDATING,Phase.REVIEWING,Phase.COMMITTED,Phase.PUBLISHED} and paths.intersection(s.changed_paths) for s in states)
