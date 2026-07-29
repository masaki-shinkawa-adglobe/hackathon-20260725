# Autonomous Issue Delivery

GitHub Issueの配送は、Codex上の`$issue-orchestrator`を唯一の通常入口として実行します。ユーザーは`issue_controller` CLIを直接起動せず、自然言語で依頼します。Skillはインストール済みの`issue-controller` console commandだけを呼び出し、Git、GitHub、Herdr、worktree、paneを直接操作しません。

詳細な設計は[docs/parallel-issue-controller-design.md](docs/parallel-issue-controller-design.md)、フロントドアの判断は[ADR 0001](docs/adr/0001-llm-front-door-and-post-merge-cleanup.md)を参照してください。

## 通常の使い方

Codexで次のように依頼してください。

```text
Issue 12を実装して
Issue 12をdry-runで実装して
残り全部を実装して
Issue 12の状態を確認して
Issue 12をmergeして
Issue 12をcleanupして
回答したので続けて
```

- 「Issue 12を実装して」は、そのまま実行承認です。フロントドアは`doctor`と`status`を確認してから`start --issue 12`を実行します。通常はcommit、push、PR作成、policyを満たすauto-mergeまで進みます。
- dry-runは`--no-publish`で実行します。
- `--auto`は「全部」「残り全部」を明示した場合だけ使用します。「次へ」「何か実装して」のように対象が不明な場合はIssue番号を確認します。
- `awaiting_input`では必要な質問を報告して停止します。Codexは回答を推測またはIssueへ投稿しません。回答後に「回答したので続けて」と依頼してください。
- mergeとcleanupは明示した場合だけ実行します。ただしstatusがmerge済みかつcleanup pendingを検知した場合、local cleanupは自動で再開します。

結果はIssue、phase、PR、テスト、blocker、cleanupだけを要約します。raw logやagent transcriptは返しません。cleanupの失敗は配送成功を取り消さず、warningとして報告します。

## CLIセットアップと復旧リファレンス

この節は`issue-controller`を利用可能にする管理者と、障害復旧を行う担当者向けです。日常のIssue実装では、ここにあるCLIを直接実行せず、`$issue-orchestrator`へ依頼してください。

### 前提条件

ControllerはPython 3.12以上で動作し、`git`、認証済み`gh`、`herdr`、`codex`、`/usr/bin/bwrap`、`/usr/bin/docker`を必要とします。ControllerはHerdr管理下のpaneで`HERDR_ENV=1`として動作します。

Gitleaks imageは[tools/gitleaks-image.lock](tools/gitleaks-image.lock)のdigestで固定します。実行環境にはあらかじめ取得しておきます。

```bash
docker pull "$(tr -d '\n' < tools/gitleaks-image.lock)"
docker image inspect --format '{{json .RepoDigests}}' "$(tr -d '\n' < tools/gitleaks-image.lock)"
```

### インストール

Controller用venvはIssue worktree外に作成します。`<controller-venv>`と`<repository-path>`は絶対パスへ置き換えてください。

```bash
python3 -m venv --system-site-packages <controller-venv>
<controller-venv>/bin/python -m pip install --no-deps --no-build-isolation <repository-path>
```

そのvenvの`bin`を`PATH`へ追加し、次が実行できることを確認します。

```bash
issue-controller --config config/issue-controller.toml doctor
```

`issue-controller`が未installの場合、Skillは自動install・updateしません。管理者がこの手順で利用可能にしてから、同じ自然言語依頼を再実行してください。利用可能な古いversionは許容し、version一致検査は行いません。

### 設定と診断

実運用設定は[config/issue-controller.toml](config/issue-controller.toml)です。新規環境ではexampleをコピーして対象リポジトリに合わせます。

```bash
cp config/issue-controller.example.toml config/issue-controller.toml
issue-controller --config config/issue-controller.toml doctor
issue-controller --config config/issue-controller.toml status
```

`doctor`が失敗した場合は修復してから再試行します。Controller state、lock、ログはリポジトリ外の`<repository-parent>/.herdr-issue-controller/<repository-name>/`に保存されます。

### 復旧時のコマンド対応

通常はCodexへ依頼してください。緊急の復旧手順としてのみ、管理者は以下のController commandを使用します。状態を変えるcommandの前には必ず`doctor`、`status [--issue <number>]`を順に実行します。

| 目的 | command |
|---|---|
| 状態確認 | `issue-controller --config config/issue-controller.toml status [--issue <number>]` |
| 回答後の再開 | `issue-controller --config config/issue-controller.toml resume --issue <number>` |
| dry-run成果のpublish | `issue-controller --config config/issue-controller.toml publish --issue <number>` |
| 明示merge | `issue-controller --config config/issue-controller.toml merge --issue <number> --head-sha <sha>` |
| local cleanup | `issue-controller --config config/issue-controller.toml cleanup --issue <number>` |

Controllerだけがcommit、push、PR、merge、cleanupを実行します。cleanupは所有確認済みのlocal pane、worktree、local branchを対象にし、remote branchは削除しません。失敗したcleanup resourceは復旧用に保持します。

## 運用原則

- Issue本文やagent出力は信頼できないデータとして扱い、コマンドとして実行しない。
- `start`はControllerが低権限の`issue-planner`を自動起動する。Plannerを直接実行しない。
- workerは実装とworktree内テストだけを担当する。Controllerが検証、commit、publish、merge、cleanupを担当する。
- dirtyまたは所有不明のresourceは自動削除しない。
- Controllerは状態変更前に`doctor`と`status`を確認し、同一リポジトリの複数run衝突を避ける。
