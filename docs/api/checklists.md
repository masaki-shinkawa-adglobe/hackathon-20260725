# チェックリスト取得API

## 概要

保存済みチェックリストの一覧と詳細を取得する。レスポンスには画面表示項目に加えて、画面遷移や後続操作で使用する各IDを含める。

Backlog登録状況は、配下タスクの`task_backlog_links`を集計して返す。タスクが0件または発行済みタスクが0件なら`unregistered`、一部だけ発行済みなら`partial`、全タスクが発行済みなら`registered`とする。Backlogへの課題作成、更新、削除、同期は本APIの責務に含めない。

## 一覧取得

```http
GET /checklists
```

### 成功レスポンス

```http
HTTP/1.1 200 OK
Content-Type: application/json
```

```json
{
  "checklists": [
    {
      "id": 1,
      "name": "月次決算業務",
      "task_count": 2,
      "assignee_count": 3,
      "backlog_registration": {
        "status": "partial",
        "issued_task_count": 1,
        "total_task_count": 2,
        "last_issued_at": "2026-07-31T10:00:00+09:00"
      },
      "updated_at": "2026-07-31T12:00:00+09:00"
    }
  ]
}
```

| フィールド | 型 | 説明 |
| --- | --- | --- |
| `checklists[].id` | integer | チェックリストID |
| `checklists[].name` | string | チェックリスト名 |
| `checklists[].task_count` | integer | 対象チェックリストに紐づくタスク数 |
| `checklists[].assignee_count` | integer | チェックリストの想定担当者数 |
| `checklists[].backlog_registration.status` | `unregistered` \| `partial` \| `registered` | タスク単位のBacklog登録状態 |
| `checklists[].backlog_registration.issued_task_count` | integer | Backlog発行済みタスク数 |
| `checklists[].backlog_registration.total_task_count` | integer | 配下タスク総数 |
| `checklists[].backlog_registration.last_issued_at` | string \| null | 最終発行日時。未発行なら`null` |
| `checklists[].updated_at` | string | チェックリスト最終更新日時。`checklists.updated_at` をISO 8601形式で返す |

## 詳細取得

```http
GET /checklists/{checklist_id}
```

### パスパラメータ

| パラメータ | 型 | 必須 | 説明 |
| --- | --- | --- | --- |
| `checklist_id` | integer | 必須 | 取得対象のチェックリストID |

### 成功レスポンス

```http
HTTP/1.1 200 OK
Content-Type: application/json
```

```json
{
  "id": 1,
  "name": "月次決算業務",
  "description": "月次決算の標準チェックリスト",
  "assignee_count": 3,
  "backlog_registration": {"status": "registered", "issued_task_count": 1, "total_task_count": 1, "last_issued_at": "2026-07-31T10:00:00+09:00"},
  "tasks": [
    {
      "id": 1,
      "checklist_id": 1,
      "title": "月次仕訳データの確認",
      "summary": "当月分として計上された仕訳データに入力漏れがないか確認します。",
      "estimated_hours": 2.0
    }
  ]
}
```

| フィールド | 型 | 説明 |
| --- | --- | --- |
| `id` | integer | チェックリストID |
| `name` | string | チェックリスト名 |
| `description` | string \| null | チェックリスト概要 |
| `assignee_count` | integer | チェックリストの想定担当者数 |
| `backlog_registration.status` | `unregistered` \| `partial` \| `registered` | タスク単位のBacklog登録状態 |
| `backlog_registration.issued_task_count` | integer | Backlog発行済みタスク数 |
| `backlog_registration.total_task_count` | integer | 配下タスク総数 |
| `backlog_registration.last_issued_at` | string \| null | 最終発行日時。未発行なら`null` |
| `tasks[].id` | integer | タスクID |
| `tasks[].checklist_id` | integer | 紐づくチェックリストID |
| `tasks[].title` | string | タスク名 |
| `tasks[].summary` | string | タスク概要 |
| `tasks[].estimated_hours` | number | 工数 |

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

- チェックリストの作成、編集、削除
- タスクの作成、編集、削除
- Backlog課題の作成、更新、削除、同期
- 検索、絞り込み、並び替え、ページネーション
- 認証・認可
