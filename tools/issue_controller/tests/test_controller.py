from __future__ import annotations
import json, os, stat, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from tools.issue_controller.agent_runner import HerdrAgentRunner
from tools.issue_controller.adapters import Change, WorktreeRecord
from tools.issue_controller.adapters import GitAdapter
from tools.issue_controller.adapters import HerdrAdapter
from tools.issue_controller.config import ControllerConfig, VerifyCommand, load_config
from tools.issue_controller.controller import Controller
from tools.issue_controller.gitleaks import GitleaksDocker
from tools.issue_controller.plan_schema import validate_plan
from tools.issue_controller.policy import LowRiskInput, low_risk_reasons
from tools.issue_controller.process_runner import ProcessResult, ProcessRunner
from tools.issue_controller.result_parser import review_result, worker_result
from tools.issue_controller.state import StateStore
from tools.issue_controller.validation import branch, issue_number, relative_path, worktree_path
from tools.issue_controller.gitleaks import ScanResult
from tools.issue_controller.models import ControllerState, IssueState, Phase


SHA_A = "a" * 40
SHA_B = "b" * 40


class _FakeGit:
  def __init__(self, repo):
    self.repo=repo;self.records={};self.calls=[];self.dirty=False;self.head_value=SHA_B;self.branches={}
  def fetch_base(self, base): self.calls.append(("fetch",base));return SHA_A
  def add_worktree(self,path,branch,base):
    path.mkdir(parents=True);number=path.name.removeprefix("issue-");(path/"docs").mkdir();(path/"docs"/f"{number}.md").write_text(number);self.records[path.resolve()]=branch;self.branches[branch]=SHA_B;self.calls.append(("add",branch))
  def worktrees(self): return [WorktreeRecord(path, SHA_B, branch) for path,branch in self.records.items()]
  def current_branch(self,cwd): return self.records[cwd.resolve()]
  def changes(self,cwd): return [Change(f"docs/{cwd.name}.md","?","?")]
  def diff_for_scan(self,cwd): return "diff"
  def stage(self,cwd): self.calls.append(("stage",cwd.name))
  def staged_diff_for_scan(self,cwd): return "diff"
  def commit(self,cwd,message): self.calls.append(("commit",cwd.name,message));return SHA_B
  def is_clean(self,cwd): return not self.dirty
  def head(self,cwd): return self.head_value
  def push(self,branch,base): self.calls.append(("push",branch,base))
  def branch_exists(self,branch): return branch in self.branches
  def branch_head(self,branch): return self.branches[branch]
  def remove_worktree(self,path):
    self.calls.append(("remove_worktree",path.name));self.records.pop(path.resolve());
    for child in sorted(path.rglob("*"),reverse=True):
      if child.is_file(): child.unlink()
      elif child.is_dir(): child.rmdir()
    path.rmdir()
  def delete_branch(self,branch,*,force=False): self.calls.append(("delete_branch",branch,force));self.branches.pop(branch)
  def committed_changes(self,base,head): return [Change("README.md","M"," ")]
  def committed_numstat(self,base,head): return (1,False)
  def unsafe_tree_paths(self,head,paths): return (False,False)


class _FakeGitleaks:
  def __init__(self): self.cleaned=[]
  def scan(self,*args): return ScanResult(True,False,0)
  def cleanup(self,*args): self.cleaned.append(args)


class _FakeAgents:
  def __init__(self): self.events=[];self.planner_result={"schema_version":1,"batches":[{"issues":[1,2],"reason":"independent"}],"dependencies":[],"clarifications":[],"warnings":[]};self.planner_error=None
  def start(self,**kwargs): self.events.append(("launch",kwargs["name"],kwargs["permission_profile"]));return (f"opaque-{kwargs['name']}","now")
  def collect(self,*,name,**kwargs):
    self.events.append(("collect",name))
    if "plan-" in name:
      if isinstance(self.planner_error, Exception): raise self.planner_error
      if self.planner_error: raise RuntimeError(self.planner_error)
      return type("Run",(),{"result":self.planner_result,"ended_at":"now"})()
    if "review" in name:
      result={"verdict":"OK","findings":[]}
    else:
      number=name.split("-")[1];result={"schema_version":1,"status":"done","changed_files":[f"docs/issue-{number}.md"],"tests":[],"remaining_work":[],"clarification":None,"pr_draft":{"summary":["docs"],"assumptions":[],"tests":[]}}
    return type("Run",(),{"result":result,"ended_at":"now"})()
  def _save_log(self,*args): pass


class _FakeGh:
  def __init__(self): self.created=[];self.labels=[];self.merges=[];self.pr_data={};self.comments=[]
  def issue(self,n): return {"number":n,"title":f"Issue {n}","url":f"https://example/issues/{n}","body":"","labels":[],"comments":[]}
  def existing_pr(self,branch): return None
  def create_pr(self,*args): self.created.append(args);return "https://example/pr/1"
  def pr(self,url): return self.pr_data[url]
  def set_risk_label(self,*args): self.labels.append(args)
  def merge(self,*args): self.merges.append(args)
  def comment_issue(self,*args): self.comments.append(args)

class ControllerTests(unittest.TestCase):
  def _controller_with_fakes(self, directory):
    repo=Path(directory)/"repo";repo.mkdir()
    class TestController(Controller):
      def doctor(self): return []
    controller=TestController(repo,ControllerConfig(max_parallel=2))
    controller.git=_FakeGit(repo);controller.gitleaks=_FakeGitleaks();controller.agents=_FakeAgents();controller.gh=_FakeGh()
    class Herdr:
      def __init__(self): self.closed=[];self.pane_data=[]
      def panes(self): return self.pane_data
      def close_pane(self,pane): self.closed.append(pane)
    controller.herdr=Herdr()
    return controller

  def _merged_item(self, controller, directory, *, phase=Phase.AWAITING_MERGE_APPROVAL):
    path=worktree_path(controller.repo,1);branch="issue/1-issue-1"
    controller.git.add_worktree(path,branch,SHA_A)
    item=IssueState(1,branch=branch,worktree=str(path),phase=phase,base_sha=SHA_A,commit_sha=SHA_B,pr_url="https://example/pr/1",owned_panes=["worker-pane","review-pane","risk-pane"],secret_scan_container_name="scan",secret_scan_cidfile="cid")
    controller.gh.pr_data[item.pr_url]={"state":"MERGED","headRefOid":SHA_B,"headRefName":branch,"baseRefName":"main","isDraft":False,"mergeable":"MERGEABLE","statusCheckRollup":[{"conclusion":"SUCCESS"}],"reviews":[]}
    controller.herdr.pane_data=[{"pane_id":pane,"agent_status":"idle"} for pane in item.owned_panes]
    return item

  def test_start_launches_batch_before_collect_and_commits_without_publish(self):
    with tempfile.TemporaryDirectory() as d:
      controller=self._controller_with_fakes(d)
      state=controller.start([1,2],no_publish=True)
      events=controller.agents.events
      worker_events=[event for event in events if "worker" in event[1]]
      first_collect=next(i for i,e in enumerate(worker_events) if e[0]=="collect")
      self.assertEqual([e[1] for e in worker_events[:first_collect]],["issue-1-worker","issue-2-worker"])
      self.assertEqual({state["issues"]["1"]["phase"],state["issues"]["2"]["phase"]},{"committed"})
      self.assertEqual(len({state["issues"]["1"]["worktree"],state["issues"]["2"]["worktree"]}),2)
      self.assertFalse(controller.gh.created);self.assertFalse(controller.gh.merges)
      self.assertFalse(any(call[0]=="push" for call in controller.git.calls))

  def test_fixed_verifier_runs_directly_in_issue_worktree(self):
    class Capture(ProcessRunner):
      def __init__(self): self.calls=[]
      def run(self,argv,**kwargs):
        self.calls.append((list(argv),kwargs))
        return ProcessResult(tuple(argv),0,"ok","")
    with tempfile.TemporaryDirectory() as d:
      controller=self._controller_with_fakes(d);capture=Capture();controller.runner=capture
      controller.agents.planner_result={"schema_version":1,"batches":[{"issues":[1],"reason":"independent"}],"dependencies":[],"clarifications":[],"warnings":[]}
      controller.config=ControllerConfig(max_parallel=2,verify_commands=(VerifyCommand("unit",("python3","-m","unittest"),30),))
      state=controller.start([1],no_publish=True)
      verifier=next(call for call in capture.calls if call[0]==["python3","-m","unittest"])
      self.assertEqual(verifier[1]["cwd"],Path(state["issues"]["1"]["worktree"]))
      self.assertEqual(verifier[1]["timeout"],30)

  def test_start_runs_read_only_planner_before_creating_worktrees(self):
    with tempfile.TemporaryDirectory() as d:
      controller=self._controller_with_fakes(d)
      controller.start([1,2],no_publish=True)
      self.assertEqual(controller.agents.events[0],("launch","issue-plan-" + controller.store.load().run_id,"read-only"))
      self.assertFalse(controller.store.load().planner_fallback)
      self.assertIn(("add","issue/1-issue-1"),controller.git.calls)

  def test_planner_clarification_awaits_input_without_worktree_or_worker(self):
    with tempfile.TemporaryDirectory() as d:
      controller=self._controller_with_fakes(d)
      controller.agents.planner_result={"schema_version":1,"batches":[{"issues":[1],"reason":"needs answer"}],"dependencies":[],"clarifications":[{"issue":1,"question":"公開形式は?","why_blocking":"互換性が変わるため","options":["A","B"]}],"warnings":[]}
      state=controller.start([1],no_publish=True)
      self.assertEqual(state["issues"]["1"]["phase"],"awaiting_input")
      self.assertFalse(any(call[0]=="add" for call in controller.git.calls))
      self.assertFalse(any(event[1].startswith("issue-1-worker") for event in controller.agents.events if event[0]=="launch"))
      self.assertEqual(len(controller.gh.comments),1)

  def test_invalid_planner_output_fails_closed_without_worktree(self):
    with tempfile.TemporaryDirectory() as d:
      controller=self._controller_with_fakes(d);controller.agents.planner_result={"schema_version":1,"batches":[],"dependencies":[],"clarifications":[],"warnings":[]}
      with self.assertRaisesRegex(RuntimeError,"blocked:invalid-plan"): controller.start([1],no_publish=True)
      self.assertFalse(any(call[0]=="add" for call in controller.git.calls))
      self.assertEqual(controller.store.load().planner_error,"blocked:invalid-plan")

  def test_planner_timeout_uses_only_configured_fallback(self):
    with tempfile.TemporaryDirectory() as d:
      controller=self._controller_with_fakes(d);controller.config=ControllerConfig(max_parallel=2,planner_fallback="deterministic");controller.agents.planner_error="agent timeout"
      state=controller.start([1],no_publish=True)
      self.assertTrue(state["planner_fallback"])

  def test_planner_result_parse_error_is_reported_as_planner_failure(self):
    with tempfile.TemporaryDirectory() as d:
      controller=self._controller_with_fakes(d);controller.agents.planner_error=ValueError("result marker not found")
      with self.assertRaisesRegex(RuntimeError,"blocked:planner-failed"): controller.start([1],no_publish=True)
      self.assertEqual(controller.store.load().planner_error,"blocked:planner-failed")
      self.assertFalse(any(call[0]=="add" for call in controller.git.calls))

  def test_publish_fails_closed_for_dirty_head_and_base_updates(self):
    with tempfile.TemporaryDirectory() as d:
      controller=self._controller_with_fakes(d);path=Path(d)/".worktrees"/"repo"/"issue-1";controller.git.add_worktree(path,"issue/1-issue-1",SHA_A)
      item=IssueState(1,branch="issue/1-issue-1",worktree=str(path),phase=Phase.COMMITTED,base_sha=SHA_A,commit_sha=SHA_B,worker_result={"pr_draft":{"summary":[],"assumptions":[],"tests":[]}})
      state=ControllerState(run_id="run-1",issues={"1":item})
      controller.git.dirty=True
      with self.assertRaises(RuntimeError): controller._publish(state,item)
      controller.git.dirty=False;controller.git.head_value=SHA_A
      with self.assertRaises(RuntimeError): controller._publish(state,item)
      controller.git.head_value=SHA_B
      controller.git.fetch_base=lambda _base: SHA_B
      controller._publish(state,item)
      self.assertEqual(item.phase,Phase.BLOCKED);self.assertEqual(item.last_error,"blocked:base-updated")
      self.assertFalse(controller.gh.created)

  def test_risk_gate_does_not_merge_low_without_ci_and_honors_human_elevation(self):
    with tempfile.TemporaryDirectory() as d:
      controller=self._controller_with_fakes(d);path=Path(d)/".worktrees"/"repo"/"issue-1";controller.git.add_worktree(path,"issue/1-issue-1",SHA_A)
      item=IssueState(1,branch="issue/1-issue-1",worktree=str(path),phase=Phase.PUBLISHED,base_sha=SHA_A,commit_sha=SHA_B,pr_url="https://example/pr/1",reviewer_result={"verdict":"OK","findings":[]},worker_result={"remaining_work":[]})
      state=ControllerState(run_id="run-1",issues={"1":item})
      controller.gh.pr_data[item.pr_url]={"state":"OPEN","headRefOid":SHA_B,"headRefName":item.branch,"labels":[],"isDraft":False,"mergeable":"MERGEABLE","statusCheckRollup":[],"reviews":[]}
      controller._risk_review=lambda *_:{"verdict":"OK","risk":"low","head_sha":SHA_B,"reasons":[]}
      controller._evaluate_merge(state,item)
      self.assertEqual(item.phase,Phase.AWAITING_MERGE_APPROVAL);self.assertFalse(controller.gh.merges)
      self.assertTrue(controller.gh.labels)
      controller.gh.labels.clear();item.phase=Phase.PUBLISHED
      controller.gh.pr_data[item.pr_url]["labels"]=[{"name":"risk:high"}]
      controller._evaluate_merge(state,item)
      self.assertEqual(item.phase,Phase.AWAITING_MERGE_APPROVAL);self.assertFalse(controller.gh.labels);self.assertFalse(controller.gh.merges)

  def test_explicit_merge_rejects_exact_head_mismatch(self):
    with tempfile.TemporaryDirectory() as d:
      controller=self._controller_with_fakes(d)
      item=IssueState(1,branch="issue/1-issue-1",phase=Phase.AWAITING_MERGE_APPROVAL,commit_sha=SHA_B,pr_url="https://example/pr/1")
      controller.store.save(ControllerState(run_id="run-1",issues={"1":item}))
      controller.gh.pr_data[item.pr_url]={"headRefOid":SHA_A,"headRefName":item.branch,"baseRefName":"main","state":"OPEN","isDraft":False,"mergeable":"MERGEABLE","statusCheckRollup":[{"conclusion":"SUCCESS"}],"reviews":[]}
      with self.assertRaises(RuntimeError): controller.merge(1,SHA_B)
      self.assertFalse(controller.gh.merges)

  def test_explicit_merge_cleans_only_owned_local_resources_and_stays_done(self):
    with tempfile.TemporaryDirectory() as d:
      controller=self._controller_with_fakes(d);item=self._merged_item(controller,d)
      controller.gh.pr_data[item.pr_url]["state"]="OPEN"
      controller.store.save(ControllerState(run_id="run-1",issues={"1":item}))
      result=controller.merge(1,SHA_B)
      self.assertEqual(result["phase"],"done");self.assertEqual(result["cleanup_status"],"cleaned")
      self.assertFalse(Path(item.worktree).exists());self.assertNotIn(item.branch,controller.git.branches)
      self.assertEqual(set(controller.herdr.closed),set(item.owned_panes));self.assertEqual(len(controller.gitleaks.cleaned),1)
      self.assertFalse(any(call[0]=="push" for call in controller.git.calls))

  def test_auto_merge_success_cleans_resources_without_remote_branch_operation(self):
    with tempfile.TemporaryDirectory() as d:
      controller=self._controller_with_fakes(d);item=self._merged_item(controller,d,phase=Phase.PUBLISHED)
      controller.gh.pr_data[item.pr_url]["state"]="OPEN";controller._risk_review=lambda *_:{"verdict":"OK","risk":"low","head_sha":SHA_B,"reasons":[]}
      state=ControllerState(run_id="run-1",issues={"1":item});controller._evaluate_merge(state,item)
      self.assertEqual(item.phase,Phase.DONE);self.assertEqual(item.cleanup_status,"cleaned")
      self.assertFalse(Path(item.worktree).exists());self.assertNotIn(item.branch,controller.git.branches)
      self.assertFalse(any(call[0]=="push" for call in controller.git.calls))

  def test_cleanup_warning_keeps_dirty_worktree_and_branch_after_merge(self):
    with tempfile.TemporaryDirectory() as d:
      controller=self._controller_with_fakes(d);item=self._merged_item(controller,d,phase=Phase.DONE);controller.git.dirty=True
      controller.store.save(ControllerState(run_id="run-1",issues={"1":item}))
      result=controller.cleanup(1)
      self.assertEqual(result["phase"],"done");self.assertEqual(result["cleanup_status"],"warning")
      self.assertIn("worktree is not clean",result["cleanup_error"])
      self.assertTrue(Path(item.worktree).exists());self.assertIn(item.branch,controller.git.branches)

  def test_manual_cleanup_retains_legacy_published_cleanup_with_nonforce_branch_delete(self):
    with tempfile.TemporaryDirectory() as d:
      controller=self._controller_with_fakes(d);item=self._merged_item(controller,d,phase=Phase.PUBLISHED)
      controller.gh.pr_data[item.pr_url]["state"]="OPEN";controller.store.save(ControllerState(run_id="run-1",issues={"1":item}))
      result=controller.cleanup(1)
      self.assertEqual(result["phase"],"cleaned");self.assertEqual(result["cleanup_status"],"cleaned")
      self.assertFalse(Path(item.worktree).exists());self.assertIn(("delete_branch",item.branch,False),controller.git.calls)

  def test_manual_cleanup_preserves_unpublished_commit(self):
    with tempfile.TemporaryDirectory() as d:
      controller=self._controller_with_fakes(d);path=worktree_path(controller.repo,1);branch="issue/1-issue-1";controller.git.add_worktree(path,branch,SHA_A)
      item=IssueState(1,branch=branch,worktree=str(path),phase=Phase.COMMITTED,commit_sha=SHA_B)
      controller.store.save(ControllerState(run_id="run-1",issues={"1":item}))
      with self.assertRaisesRegex(RuntimeError,"unpublished commit"):
        controller.cleanup(1)
      self.assertTrue(path.exists());self.assertIn(branch,controller.git.branches)

  def test_cleanup_warning_keeps_resources_when_worktree_removal_fails(self):
    with tempfile.TemporaryDirectory() as d:
      controller=self._controller_with_fakes(d);item=self._merged_item(controller,d,phase=Phase.DONE)
      controller.git.remove_worktree=lambda _path: (_ for _ in ()).throw(RuntimeError("remove failed"))
      controller.store.save(ControllerState(run_id="run-1",issues={"1":item}))
      result=controller.cleanup(1)
      self.assertEqual(result["phase"],"done");self.assertEqual(result["cleanup_status"],"warning")
      self.assertIn("worktree cleanup failed",result["cleanup_error"])
      self.assertTrue(Path(item.worktree).exists());self.assertIn(item.branch,controller.git.branches)

  def test_done_cleanup_turns_merge_verification_failure_into_warning(self):
    with tempfile.TemporaryDirectory() as d:
      controller=self._controller_with_fakes(d);item=self._merged_item(controller,d,phase=Phase.DONE)
      controller.gh.pr=lambda _url: (_ for _ in ()).throw(RuntimeError("GitHub unavailable"))
      controller.store.save(ControllerState(run_id="run-1",issues={"1":item}))
      result=controller.cleanup(1)
      self.assertEqual(result["phase"],"done");self.assertEqual(result["cleanup_status"],"warning")
      self.assertIn("merge verification failed",result["cleanup_error"])
      self.assertTrue(Path(item.worktree).exists());self.assertIn(item.branch,controller.git.branches)

  def test_cleanup_does_not_close_working_or_unowned_panes(self):
    with tempfile.TemporaryDirectory() as d:
      controller=self._controller_with_fakes(d);item=self._merged_item(controller,d,phase=Phase.DONE)
      controller.herdr.pane_data=[{"pane_id":"worker-pane","agent_status":"working"},{"pane_id":"unowned-pane","agent_status":"idle"}]
      controller.store.save(ControllerState(run_id="run-1",issues={"1":item}))
      result=controller.cleanup(1)
      self.assertEqual(result["cleanup_status"],"warning");self.assertIn("still working",result["cleanup_error"])
      self.assertNotIn("worker-pane",controller.herdr.closed);self.assertNotIn("unowned-pane",controller.herdr.closed)
      self.assertTrue(Path(item.worktree).exists());self.assertIn(item.branch,controller.git.branches)

  def test_status_detects_external_merge_but_leaves_cleanup_pending(self):
    with tempfile.TemporaryDirectory() as d:
      controller=self._controller_with_fakes(d);item=self._merged_item(controller,d,phase=Phase.PUBLISHED)
      controller.store.save(ControllerState(run_id="run-1",issues={"1":item}))
      result=controller.status(1)
      self.assertEqual(result["phase"],"done");self.assertEqual(result["cleanup_status"],"pending")
      self.assertTrue(Path(item.worktree).exists());self.assertIn(item.branch,controller.git.branches)
      self.assertFalse(controller.herdr.closed);self.assertFalse(controller.gitleaks.cleaned)

  def test_resume_detects_existing_merge_and_cleans_up(self):
    with tempfile.TemporaryDirectory() as d:
      controller=self._controller_with_fakes(d);item=self._merged_item(controller,d,phase=Phase.PUBLISHED)
      controller.store.save(ControllerState(run_id="run-1",issues={"1":item}))
      result=controller.resume(1)
      self.assertEqual(result["issues"]["1"]["phase"],"done");self.assertEqual(result["issues"]["1"]["cleanup_status"],"cleaned")
      self.assertFalse(Path(item.worktree).exists());self.assertNotIn(item.branch,controller.git.branches)

  def test_worker_reviewer_and_risk_panes_are_recorded_as_owned(self):
    with tempfile.TemporaryDirectory() as d:
      controller=self._controller_with_fakes(d);controller.agents.planner_result={"schema_version":1,"batches":[{"issues":[1],"reason":"independent"}],"dependencies":[],"clarifications":[],"warnings":[]};state=controller.start([1],no_publish=True)
      persisted=controller.store.load();item=persisted.issues["1"]
      self.assertTrue(any("worker" in pane for pane in item.owned_panes));self.assertTrue(any("review" in pane for pane in item.owned_panes))
      controller.agents.collect=lambda **_:type("Run",(),{"result":{"verdict":"OK","risk":"low","head_sha":SHA_B,"reasons":[]},"ended_at":"now"})()
      controller._risk_review(persisted,item)
      self.assertTrue(any("risk" in pane for pane in item.owned_panes));self.assertTrue(any("risk" in pane for pane in controller.store.load().issues["1"].owned_panes));self.assertEqual(state["issues"]["1"]["phase"],"committed")

  def test_legacy_state_fields_and_cleaned_phase_remain_readable(self):
    value={"issue_number":1,"phase":"cleaned","pane_id":"legacy-pane"}
    item=IssueState.from_dict(value)
    self.assertEqual(item.phase,Phase.CLEANED);self.assertEqual(item.owned_panes,[]);self.assertEqual(item.cleanup_status,"cleaned")
    with tempfile.TemporaryDirectory() as d:
      controller=self._controller_with_fakes(d);item.branch="issue/1-issue-1";item.pr_url="https://example/pr/1";item.commit_sha=SHA_B
      controller.gh.pr_data[item.pr_url]={"state":"MERGED","headRefOid":SHA_B,"headRefName":item.branch}
      controller.store.save(ControllerState(run_id="run-1",issues={"1":item}))
      result=controller.cleanup(1)
      self.assertEqual(result["phase"],"done");self.assertEqual(result["cleanup_status"],"cleaned")
  def test_agent_profile_argv_uses_builtin_profiles_only(self):
    class FakeHerdr:
      def split(self, cwd): self.cwd=cwd; return "opaque-pane"
      def start(self, pane, name, argv): self.pane=pane;self.name=name;self.argv=argv
      def prompt(self, name, prompt): self.prompt_value=prompt
    with tempfile.TemporaryDirectory() as d:
      worktree=Path(d)/"worktree";worktree.mkdir()
      fake=FakeHerdr()
      with patch.dict(os.environ,{"CODEX_HOME":str(Path(d)/"codex")},clear=False):
        HerdrAgentRunner(fake,Path(d)/"logs").start(cwd=worktree,name="issue-1-worker",model="model",reasoning_effort="medium",permission_profile="workspace",prompt="x")
      self.assertIn('default_permissions=":workspace"',fake.argv)
      self.assertIn("--ask-for-approval",fake.argv);self.assertIn("never",fake.argv)
      self.assertNotIn("--sandbox",fake.argv);self.assertNotIn("--add-dir",fake.argv)
      with patch.dict(os.environ,{"CODEX_HOME":str(Path(d)/"codex")},clear=False):
        HerdrAgentRunner(fake,Path(d)/"logs").start(cwd=worktree,name="issue-1-review",model="model",reasoning_effort="high",permission_profile="read-only",prompt="x")
      self.assertIn('default_permissions=":read-only"',fake.argv)
  def test_herdr_adapter_preserves_opaque_pane_id_and_current_argv(self):
    class Runner(ProcessRunner):
      def __init__(self): self.argv=[]
      def checked(self, argv, **kwargs):
        self.argv.append(list(argv));return type("R",(),{"stdout":json.dumps({"result":{"pane":{"pane_id":"pane:opaque/1"}}})})()
    runner=Runner();adapter=HerdrAdapter(runner)
    self.assertEqual(adapter.split(Path("/tmp")),"pane:opaque/1")
    self.assertEqual(runner.argv[0][:6],["herdr","pane","split","--current","--direction","right"])

  def test_herdr_prompt_waits_for_post_submission_state_change(self):
    class Runner(ProcessRunner):
      def __init__(self): self.argv=[]
      def checked(self, argv, **kwargs):
        self.argv.append(list(argv));return ProcessResult(tuple(argv),0,"","")
    runner=Runner();HerdrAdapter(runner).prompt("issue-1-worker","implement")
    self.assertEqual(
      runner.argv[0],
      ["herdr","agent","prompt","issue-1-worker","implement","--wait","--until","working","--until","idle","--until","done","--until","blocked","--timeout","30000"],
    )
  def test_agent_rejects_legacy_user_config_layer(self):
    class FakeHerdr: pass
    with tempfile.TemporaryDirectory() as d:
      worktree=Path(d)/"worktree";worktree.mkdir();home=Path(d)/"codex";home.mkdir();(home/"config.toml").write_text('sandbox_mode="workspace-write"\n')
      with patch.dict(os.environ,{"CODEX_HOME":str(home)},clear=False):
        with self.assertRaises(RuntimeError): HerdrAgentRunner(FakeHerdr(),Path(d)/"logs").start(cwd=worktree,name="issue-1-worker",model="model",reasoning_effort="medium",permission_profile="workspace",prompt="x")
  def test_input_validation(self):
    self.assertEqual(issue_number("12"),12)
    for v in [0,"01","-1",True]:
      with self.assertRaises(ValueError): issue_number(v)
    self.assertEqual(branch(12,"Hello, World!",base="main"),"issue/12-hello-world")
    for p in ["../x","/x","x\\y"]:
      with self.assertRaises(ValueError): relative_path(p)
  def test_worktree_path(self):
    with tempfile.TemporaryDirectory() as d:
      repo=Path(d)/"repo";repo.mkdir();self.assertEqual(worktree_path(repo,3),Path(d)/".worktrees/repo/issue-3")
  def test_temporary_git_repository_ref_format(self):
    with tempfile.TemporaryDirectory() as d:
      repo=Path(d)/"repo";repo.mkdir()
      ProcessRunner().checked(["git","init","--quiet"],cwd=repo)
      self.assertEqual(branch(7,"Ref format",base="main",runner=ProcessRunner()),"issue/7-ref-format")
  def test_git_status_parser_handles_rename_and_untracked_in_temporary_repo(self):
    with tempfile.TemporaryDirectory() as d:
      repo=Path(d)/"repo";repo.mkdir();runner=ProcessRunner()
      runner.checked(["git","init","--quiet"],cwd=repo)
      runner.checked(["git","config","user.email","test@example.invalid"],cwd=repo);runner.checked(["git","config","user.name","Test"],cwd=repo)
      (repo/"before.txt").write_text("before\n");runner.checked(["git","add","before.txt"],cwd=repo);runner.checked(["git","commit","--quiet","-m","initial"],cwd=repo)
      runner.checked(["git","mv","before.txt","after.txt"],cwd=repo);(repo/"untracked.txt").write_text("new\n")
      changes=GitAdapter(runner,repo).changes(repo)
      renamed=next(change for change in changes if change.path=="after.txt")
      self.assertTrue(renamed.renamed);self.assertEqual(renamed.original_path,"before.txt")
      self.assertEqual(next(change for change in changes if change.path=="untracked.txt").index_status,"?")
  def test_plan_rejects_commands_and_cycle(self):
    good={"schema_version":1,"batches":[{"issues":[1,2],"reason":"x"}],"dependencies":[],"clarifications":[],"warnings":[]}
    self.assertEqual(validate_plan(good,{1,2},2),good)
    with self.assertRaises(ValueError):validate_plan({**good,"command":"echo bad"},{1,2},2)
    cyc={**good,"dependencies":[{"before":1,"after":2,"reason":"x"},{"before":2,"after":1,"reason":"x"}]}
    with self.assertRaises(ValueError):validate_plan(cyc,{1,2},2)
  def test_controller_persists_deterministic_plan_outside_repo(self):
    with tempfile.TemporaryDirectory() as d:
      repo=Path(d)/"repo";repo.mkdir()
      c=Controller(repo,ControllerConfig())
      plan=c.plan([9,2])
      self.assertEqual(plan["batches"][0]["issues"],[2,9])
      self.assertTrue((Path(d)/".herdr-issue-controller/repo/state.json").exists())
  def test_state_atomic_and_lock(self):
    with tempfile.TemporaryDirectory() as d:
      s=StateStore(Path(d));s.save(s.load());self.assertEqual(s.load().version,1)
      with s.lock():
        with self.assertRaises(RuntimeError):
          with StateStore(Path(d)).lock(): pass
      (Path(d)/"state.json").write_text("{")
      with self.assertRaises(RuntimeError):s.load()
  def test_result_schemas(self):
    worker={"schema_version":1,"status":"done","changed_files":["a.py"],"tests":[],"remaining_work":[],"clarification":None,"pr_draft":{"summary":[],"assumptions":[],"tests":[]}}
    self.assertEqual(worker_result(json.dumps(worker))["status"],"done")
    risk={"verdict":"OK","risk":"low","head_sha":"a"*40,"reasons":[]}
    self.assertEqual(review_result(json.dumps(risk),True)["risk"],"low")
  def test_low_risk_is_fail_closed_and_human_wins(self):
    good=LowRiskInput(("README.md",),1,1,"low",True,True,True,False)
    self.assertEqual(low_risk_reasons(good,ControllerConfig()),[])
    self.assertTrue(low_risk_reasons(LowRiskInput(("README.md",),1,1,"low",True,True,True,True),ControllerConfig()))
  def test_gitleaks_argv_is_hardened_and_no_mount_of_repo(self):
    class Capture(ProcessRunner):
      def run(self,argv,**kwargs):
        if argv[:3] == ["docker","container","inspect"]:
          return type("R",(),{"returncode":1,"stdout":"","stderr":""})()
        self.argv=list(argv);self.kwargs=kwargs;return type("R",(),{"returncode":0,"stdout":"","stderr":""})()
    with tempfile.TemporaryDirectory() as d:
      lock=Path(d)/"lock";lock.write_text("example/gitleaks@sha256:"+"a"*64)
      r=Capture();g=GitleaksDocker("docker",lock,Path(d),r);g.scan("secret", "run-1", 2, 3)
      self.assertIn("--rm",r.argv);self.assertIn("--network=none",r.argv);self.assertIn("--read-only",r.argv);self.assertIn("--cap-drop=ALL",r.argv);self.assertIn("--security-opt=no-new-privileges",r.argv);self.assertIn("--cidfile",r.argv);self.assertEqual(r.kwargs["input_text"],"secret")
  def test_gitleaks_cleanup_requires_matching_labels_before_removal(self):
    class Capture(ProcessRunner):
      def __init__(self, labels): self.labels=labels;self.argv=[]
      def run(self,argv,**kwargs):
        self.argv.append(list(argv))
        if argv[1:3]==["container","inspect"]:
          return type("R",(),{"returncode":0,"stdout":json.dumps(self.labels),"stderr":""})()
        return type("R",(),{"returncode":0,"stdout":"","stderr":""})()
    with tempfile.TemporaryDirectory() as d:
      lock=Path(d)/"lock";lock.write_text("example/gitleaks@sha256:"+"a"*64);root=Path(d)/"state"
      good=Capture({"io.issue-controller.run":"run-1","io.issue-controller.issue":"2"});g=GitleaksDocker("docker",lock,root,good)
      cid=g.cidfile("run-1",2,1);cid.parent.mkdir();cid.write_text("opaque")
      g.cleanup("run-1",2,1,g.name("run-1",2,1),str(cid))
      self.assertFalse(cid.exists());self.assertTrue(any(argv[1:4]==["container","rm","--force"] for argv in good.argv))
      bad=Capture({"io.issue-controller.run":"other","io.issue-controller.issue":"2"});bad_g=GitleaksDocker("docker",lock,root,bad)
      with self.assertRaisesRegex(RuntimeError,"ownership mismatch"):
        bad_g.cleanup("run-1",2,1,bad_g.name("run-1",2,1),None)
      self.assertFalse(any(argv[1:4]==["container","rm","--force"] for argv in bad.argv))
  def test_legacy_sandbox_config_is_rejected(self):
    with tempfile.TemporaryDirectory() as d:
      path=Path(d)/"config.toml"
      path.write_text('version=1\n[worker]\nsandbox_mode="workspace-write"\n')
      with self.assertRaises(ValueError): load_config(path)
  def test_docker_runtime_defaults_to_path_lookup(self):
    with tempfile.TemporaryDirectory() as d:
      path=Path(d)/"config.toml";path.write_text("version=1\n")
      self.assertEqual(load_config(path).docker,"docker")
  def test_doctor_reports_missing_path_command_without_crashing(self):
    class DoctorRunner(ProcessRunner):
      def run(self,argv,**kwargs):
        if argv[0]=="docker": raise RuntimeError("cannot execute: docker")
        return ProcessResult(tuple(argv),0,"","")
    with tempfile.TemporaryDirectory() as d:
      repo=Path(d)/"repo";repo.mkdir()
      controller=Controller(repo,ControllerConfig(),DoctorRunner())
      controller.git=type("Git",(),{"verify_repository":lambda self:None})()
      controller.herdr=type("Herdr",(),{"help_commands":lambda self:[],"current_pane":lambda self:None,"panes":lambda self:[],"agents":lambda self:[]})()
      controller.gh=type("Gh",(),{"repo":lambda self:{}})()
      controller.gitleaks=type("Gitleaks",(),{"verify_image_is_local":lambda self:None})()
      with patch.dict(os.environ,{"HERDR_ENV":"1","CODEX_HOME":str(Path(d)/"codex")},clear=False):
        self.assertIn("missing required docker",controller.doctor())
  def test_fake_executable_uses_literal_argv(self):
    with tempfile.TemporaryDirectory() as d:
      f=Path(d)/"fake";out=Path(d)/"out";f.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$OUTPUT\"\n");f.chmod(f.stat().st_mode|stat.S_IXUSR)
      os.environ["OUTPUT"]=str(out);ProcessRunner().checked([str(f),";touch never","two words"])
      self.assertEqual(out.read_text().splitlines(),[";touch never","two words"])

if __name__=="__main__":unittest.main()
