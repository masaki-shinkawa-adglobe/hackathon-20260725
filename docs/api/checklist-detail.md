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
  "backlog_registration": {"status": "registered", "issued_task_count": 1, "total_task_count": 1, "last_issued_at": "2026-07-31T10:00:00+09:00"},
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
| `backlog_registration.status` | `unregistered` \| `partial` \| `registered` | タスク単位のBacklog登録状態 |
| `backlog_registration.issued_task_count` | integer | Backlog発行済みタスク数 |
| `backlog_registration.total_task_count` | integer | 配下タスク総数 |
| `backlog_registration.last_issued_at` | string \| null | 最終発行日時。未発行なら`null` |
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
