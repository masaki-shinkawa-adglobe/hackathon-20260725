# チェックリスト編集API

## エンドポイント

```http
PATCH /checklists/{checklist_id}
Content-Type: application/json
```

## リクエスト

### パスパラメータ

| パラメータ | 型 | 必須 | 説明 |
| --- | --- | --- | --- |
| `checklist_id` | integer | 必須 | 編集対象のチェックリストID |

```json
{
  "name": "月次決算業務（改訂版）",
  "description": "月次決算の標準チェックリストです。",
  "assignee_count": 3,
  "backlog_project_key_or_url": "https://example.backlog.com/projects/PROJ"
}
```

| フィールド | 型 | 必須 | 制約 | 説明 |
| --- | --- | --- | --- | --- |
| `name` | string | 必須 | 1〜255文字 | チェックリスト名 |
| `description` | string \| null | 任意 | 空文字列を許容 | チェックリストの説明 |
| `assignee_count` | integer | 必須 | 1以上 | 担当者人数 |
| `backlog_project_key_or_url` | string \| null | 任意 | 自由入力 | BacklogのプロジェクトキーまたはURL |

## 成功レスポンス

```http
HTTP/1.1 200 OK
Content-Type: application/json
```

```json
{
  "id": 1,
  "name": "月次決算業務（改訂版）",
  "description": "月次決算の標準チェックリストです。",
  "assignee_count": 3,
  "backlog_project_key_or_url": "https://example.backlog.com/projects/PROJ"
}
```

## 主要フィールド

| フィールド | 型 | 説明 |
| --- | --- | --- |
| `id` | integer | 編集したチェックリストID |
| `name` | string | 編集後のチェックリスト名 |
| `description` | string \| null | 編集後のチェックリストの説明 |
| `assignee_count` | integer | 編集後の担当者人数 |
| `backlog_project_key_or_url` | string \| null | 入力されたBacklogのプロジェクトキーまたはURL |

## エラーレスポンス

### バリデーションエラー

```http
HTTP/1.1 422 Unprocessable Entity
```

`checklist_id`、`name`、`assignee_count` などが制約を満たさない場合に返す。

### 存在しないチェックリスト

```http
HTTP/1.1 404 Not Found
Content-Type: application/json
```

```json
{
  "detail": "Checklist not found"
}
```

## 対象外

- タスクの作成、編集、削除
- Backlog課題の作成、更新、削除、双方向同期
- 認証・認可
- Web実装時のブラウザからFastAPIへの直接通信。ADR 0002に従い、Next.jsサーバー側を通信境界とする
