# チェックリスト詳細取得API

## エンドポイント

```http
GET /checklists/{checklist_id}
```

## リクエスト

### パスパラメータ

| パラメータ | 型 | 必須 | 説明 |
| --- | --- | --- | --- |
| `checklist_id` | integer | 必須 | 取得対象のチェックリストID |

## 成功レスポンス

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
  "backlog_registration": {
    "is_registered": true,
    "link_id": 10,
    "backlog_issue_id": 12345,
    "backlog_issue_key": "PROJ-100",
    "backlog_issue_url": "https://example.backlog.com/view/PROJ-100"
  },
  "tasks": [
    {
      "id": 1,
      "checklist_id": 1,
      "title": "月次仕訳データの確認",
      "summary": "当月分の仕訳データに入力漏れがないか確認します。",
      "estimated_hours": 2.0
    }
  ]
}
```

## 主要フィールド

| フィールド | 型 | 説明 |
| --- | --- | --- |
| `id` | integer | チェックリストID。画面で非表示でも後続操作に使用する |
| `name` | string | チェックリスト名 |
| `description` | string \| null | チェックリストの説明 |
| `assignee_count` | integer | チェックリストの想定担当者数 |
| `backlog_registration.is_registered` | boolean | Backlog課題と紐づいているか |
| `backlog_registration.link_id` | integer \| null | チェックリストBacklog紐づきID。未登録時は `null` |
| `backlog_registration.backlog_issue_id` | integer \| null | Backlog課題ID。未登録時は `null` |
| `backlog_registration.backlog_issue_key` | string \| null | Backlog課題キー。未登録時は `null` |
| `backlog_registration.backlog_issue_url` | string \| null | Backlog課題URL。未登録時は `null` |
| `tasks[].id` | integer | タスクID。画面で非表示でも後続操作に使用する |
| `tasks[].checklist_id` | integer | 紐づくチェックリストID |
| `tasks[].title` | string | タスクタイトル |
| `tasks[].summary` | string | タスク本文 |
| `tasks[].estimated_hours` | number | 工数。0より大きい有限数 |

## エラーレスポンス

### バリデーションエラー

```http
HTTP/1.1 422 Unprocessable Entity
```

`checklist_id` が整数として不正な場合は、FastAPI/Pydantic標準のバリデーションエラー形式を返す。

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

- チェックリストおよびタスクの作成、編集、削除
- Backlog課題の作成、更新、削除、双方向同期
- 認証・認可
- Web実装時のブラウザからFastAPIへの直接通信。ADR 0002に従い、Next.jsサーバー側を通信境界とする
