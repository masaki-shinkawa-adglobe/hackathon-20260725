# Issue Agents・Web開発環境

このリポジトリには、GitHub Issueの要件整理から実装・レビュー・Draft PR作成までを役割分担して進めるIssue Agent Skillsと、Next.js・FastAPI・PostgreSQLによるWebアプリケーションのローカル開発環境が含まれています。

## リポジトリ構成

```text
.agents/skills/
  issue-requirements-interviewer/  # 要件整理とIssue作成
  issue-orchestrator/              # 1件のIssue実装を進行
  issue-planner/                   # 実装計画
  issue-implementer/               # 実装とテスト
  issue-reviewer/                  # 読み取り専用レビュー
apps/
  web/                             # Next.jsフロントエンド
  api/                             # FastAPIバックエンドとAlembic
compose.yaml                       # Web・API・DB・マイグレーション
docs/adr/                          # アーキテクチャ決定記録
```

## Issue Agent Skills

### 要件整理

`issue-requirements-interviewer`は、既存文書・コード・Issue・PRを調査し、利用者へのヒアリングを通じて合意した実装単位をGitHub Issueにします。実装、PR作成、レビュー、マージは行いません。

### Issue実装フロー

`issue-orchestrator`は1件のGitHub Issueを受け取り、次の3役を順番に呼び出します。

```text
Issue Orchestrator
  → Issue Planner
  → Issue Implementer
  → Issue Reviewer
```

- Plannerは関連コードとテストを読み、実装計画だけを作成します。
- Implementerは計画に沿って実装とテストを行います。
- Reviewerは変更を編集せず、Issueの完了条件、差分、テスト結果を独立して確認します。
- Reviewerが変更を要求した場合は、同じImplementerが修正し、同じReviewerが再レビューします。
- Reviewerが承認した変更だけをOrchestratorがcommit・pushし、GitHub CLIでDraft PRを作成します。

OrchestratorはHerdrを利用できる場合、各役を専用paneで実行します。利用できない場合はCodexサブエージェントへフォールバックします。

### 役割別モデル

| Skill | モデル | reasoning effort |
| --- | --- | --- |
| Issue Requirements Interviewer | `gpt-5.6-sol` | `medium` |
| Issue Orchestrator | `gpt-5.6-sol` | `medium` |
| Issue Planner | `gpt-5.6-terra` | `medium` |
| Issue Implementer | `gpt-5.6-terra` | `medium` |
| Issue Reviewer | `gpt-5.6-sol` | `high` |

Requirements InterviewerとOrchestratorの設定は、直接呼び出す際の推奨値です。OrchestratorはPlanner、Implementer、Reviewerを表の設定で起動し、指定モデルを利用できない場合は別モデルへ自動で切り替えず`BLOCKED`として報告します。

## 前提ツール

| 項目 | 要否 | 用途・条件 |
| --- | --- | --- |
| Codex | 必須 | Issue Agent Skillsの実行 |
| Git | 必須 | 差分、branch、commit、pushの管理 |
| GitHub CLI（`gh`） | Issue実装フローで必須 | Draft PR作成。事前に認証が必要 |
| Docker・Docker Compose v2.24以上 | Web開発で必須 | Web・API・DBの起動と検証 |
| Herdr | 任意 | Agentごとのpane分離。不在時はCodexサブエージェントを使用 |
| `HERDR_ENV=1` | Herdr利用時のみ必須 | Herdr管理pane内であることの判定 |

macOSとLinuxではDockerを利用します。Windowsでは、WSL 2のUbuntu上でリポジトリ、Codex、Git、GitHub CLIを操作し、Docker DesktopのWSL連携を使用してください。

Node.js、pnpm、Python、uv、PostgreSQLはDockerコンテナ内に用意されるため、通常の起動ではホストへのインストールは不要です。

## Webアプリケーション

| 領域 | 構成 |
| --- | --- |
| Web | Node.js 24、pnpm 11.16.0、Next.js 16.2.9、React 19、TypeScript、App Router、Tailwind CSS 4.3 |
| API | Python 3.12、FastAPI、uv、SQLAlchemy 2.x、asyncpg |
| Database | PostgreSQL 18、Alembic |
| 開発環境 | Docker Compose、Compose Watch |

構成の設計判断は[ADR 0002](docs/adr/0002-fastapi-nextjs-monorepo-development.md)を参照してください。

### 環境変数

コミット済みの`.env.local`には、ローカル開発用PostgreSQLの非秘密設定が定義されています。APIキーなどの秘密情報が必要な場合は、Git管理されない`.env`へ記載します。

```bash
cp .env.example .env
```

### 起動

```bash
docker compose up --build --watch
```

Composeは次の順序でサービスを起動します。

```text
db healthy
  → migrate completed
    → api healthy
      → web
```

| サービス | URL・公開範囲 |
| --- | --- |
| Next.js | `http://localhost:3000` |
| FastAPI | `http://localhost:8000` |
| FastAPI health check | `http://localhost:8000/health` |
| PostgreSQL | Compose内部だけで公開 |

Next.jsの初期画面はServer ComponentからFastAPIの`GET /health`を呼び出し、APIとPostgreSQLの疎通状態を表示します。PostgreSQLのデータは名前付きVolume `postgres_data`へ保存されます。

### 終了

```bash
docker compose down
```

このコマンドでは名前付きVolumeを削除しないため、PostgreSQLのデータは保持されます。

### パイロット確認用の初期データ

以下はローカル開発・パイロット確認専用のデータです。本番環境では実行しないでください。Gemini APIキーや外部サービスへの接続は不要です。

Issue #120 の優先順位対応を含むマイグレーションを適用した後、DBを起動して seeder を実行します。

```bash
docker compose up -d --build --wait db migrate api
docker compose --profile seed run --rm seed
```

seeder は複数チェックリストと合計20件のタスクを作成します。同じ固定チェックリスト名が1件でも存在する場合は、重複作成や既存データの削除を行わず終了します。Issue #120 が未適用の場合は、データを書き込まず適用を促すエラーで終了します。

タスク優先順位はDB/API値として `low`、`medium`、`high` を使用し、画面表示の低・中・高に対応します。優先順位未指定時の既定値は `medium` です。

実行後、一覧からIDを取得し、詳細を確認できます。

```bash
curl http://localhost:8000/checklists
curl http://localhost:8000/checklists/<checklist_id>
```

### ホストでの補助コマンド

ホストにNode.js 24とpnpm 11.16.0を用意している場合に限り、Webアプリケーションへ次のコマンドを直接実行できます。

```bash
pnpm install --frozen-lockfile
pnpm lint
pnpm build
```
