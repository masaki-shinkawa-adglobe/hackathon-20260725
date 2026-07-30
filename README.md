# Issue Agents

## Issue実装フロー

```text
利用者
  → Issue Orchestrator
    → Issue Planner
    → Issue Implementer
    → Issue Reviewer
```

- Orchestratorは1件のIssueを受け取り、ほかの3役を順番に呼び出します。
- Plannerは実装計画だけを作成します。
- Implementerは計画に沿って実装とテストを行います。
- Reviewerは変更を編集せずにレビューします。

## 要件整理

`issue-requirements-interviewer`は、新しい要件を整理して実装前のIssueを作成する独立Skillです。Issue実装フローからは呼び出しません。

## Windows＋WSL環境の前提ツール

| 項目 | 要否 | 用途・条件 |
|---|---|---|
| Windows 11＋WSL 2＋Ubuntu | 必須 | 開発環境の実行基盤 |
| Codex | 必須 | 各Issue Agent Skillの実行 |
| リポジトリ同梱のIssue Agent Skills | 必須 | Planner・Implementer・Reviewer・Orchestrator・Requirements Interviewer |
| Git | 必須 | 差分管理、branch、commit、push |
| GitHub CLI（`gh`） | 必須 | OrchestratorによるDraft PR作成。事前に認証が必要 |
| Docker Desktop＋Docker Compose v2.24以上 | 必須 | Web・API・DBの起動と実装検証 |
| Herdr | 任意（推奨） | Agentごとのpane分離。不在時はCodexサブエージェントへフォールバック |
| `HERDR_ENV=1` | Herdr利用時のみ必須 | Herdr管理pane内であることの判定 |
| Node.js・pnpm | ホスト側は不要 | Dockerコンテナ内で管理 |
| Python・uv・PostgreSQL | ホスト側は不要 | Dockerコンテナ内で管理 |
| VS Code WSL拡張 | 任意 | WSL内リポジトリの編集支援 |

## Webアプリケーション開発環境

Webアプリケーションは、既存のIssue Controllerと同じリポジトリ内に次のモノレポ構成で配置します。設計判断は[ADR 0002](docs/adr/0002-fastapi-nextjs-monorepo-development.md)を参照してください。

```text
apps/
  web/  # Next.js 16.2.9、TypeScript、App Router、Tailwind CSS
  api/  # Python 3.12、FastAPI、uv、SQLAlchemy、Alembic
```

ローカル開発ではDocker Composeを使用し、Next.js、FastAPI、PostgreSQL 18、マイグレーションを起動します。

```bash
docker compose up --build --watch
```

- Next.js: `http://localhost:3000`
- FastAPI: `http://localhost:8000`
- PostgreSQLはCompose内部だけで公開し、名前付きVolumeへデータを保存する
- DBのhealthy後にAlembicを実行し、成功後にFastAPIとNext.jsを起動する
- Next.jsの初期画面はFastAPIの`GET /health`をサーバー側から呼び、APIとDBの状態を表示する

`.env.local`にはコミット可能なローカルDB設定だけを置きます。`AI_API_KEY`などの秘密情報はGit管理しない`.env`へ置き、キー名だけを`.env.example`へ記載します。

初期構築では、業務機能、認証・認可、CORS、自動テスト、GitHub Actions、本番デプロイを対象外とします。
