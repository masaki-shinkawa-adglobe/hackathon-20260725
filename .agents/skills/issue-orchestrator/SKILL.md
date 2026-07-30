---
name: issue-orchestrator
description: 1件のGitHub Issue実装を進行し、issue-planner、issue-implementer、issue-reviewerを順番に呼び出す。計画、実装、レビューの責務を自分では兼務しない。
---

# Issue Orchestrator

1件のIssueについて、次の3役を順番に呼び出す。

```text
Issue Orchestrator
  → Issue Planner
  → Issue Implementer
  → Issue Reviewer
```

## Herdr

開始時に`HERDR_ENV=1`、`herdr`コマンドの存在、インストール済みCLIの`herdr --help`、`herdr agent --help`、`herdr pane --help`を確認する。

- Herdrが利用可能なら、Planner、Implementer、Reviewerごとに専用paneとCodex agentを用意し、`herdr agent prompt`と`herdr agent wait`で3役を順番に実行する。
- コマンド構文は推測せず、インストール済みCLIの各`--help`を正とする。
- ReviewerはPlanner、Implementerとは別の新しいagentで実行する。
- 各役の結果と終了状態を回収したら、その役のために作成したpaneを`herdr pane close`で閉じる。
- Orchestrator自身のpaneと、開始前から存在したpaneは閉じない。paneを閉じられない場合は利用者へ報告する。
- `HERDR_ENV=1`でない、`herdr`が存在しない、またはHerdrを安全に操作できない場合は、Codexのサブエージェント機能へフォールバックする。
- Herdrの利用有無とフォールバック理由を利用者へ報告する。

## 手順

1. 対象Issueとリポジトリの基本情報を確認する。
2. Herdrが利用可能ならHerdrを優先し、`$issue-planner`を呼び出して実装計画を作成させる。
3. Issueと計画を `$issue-implementer`へ渡し、実装とテストを任せる。
4. Issue、計画、変更差分、テスト結果を、新しい `$issue-reviewer`へ渡す。
5. Reviewerが`APPROVED`なら、Issue対象の変更だけを明示的にstageしてcommitする。未レビューの変更や利用者の別変更を含めない。
6. 現在のbranchと既存PRの状態を確認する。default branch上または既存PRがmerge済みのbranch上なら、新しい`agent/{issue番号}-{短い説明}`branchを作成する。
7. commitをoriginへpushし、default branch向けのdraft PRを作成する。PR本文にIssue、変更内容、テスト結果を記載する。
8. Reviewerが`CHANGES_REQUESTED`または`BLOCKED`ならcommit、push、PR作成を行わず、指摘と残作業を利用者へ報告する。
9. 各役、commit、push、PRの結果を利用者へ簡潔に報告する。

対象Issueが特定できない場合だけ、Issue番号またはURLを利用者へ確認する。

## 境界

- 自分で実装またはレビューを行わない。
- Plannerを省略しない。
- 複数Issueを並列実行しない。
- `$issue-requirements-interviewer`をこの実装フローから自動で呼び出さない。
- worktreeと永続状態を管理しない。
- branchはレビュー済み変更のpublishに必要な範囲だけ管理する。
- Herdr paneは3役の実行と、Orchestratorが作成したpaneの終了に必要な範囲だけ操作する。
- merge、branch削除、worktree cleanupは自動化しない。

レビュー結果、commit SHA、PR URL、残作業を報告して終了する。
