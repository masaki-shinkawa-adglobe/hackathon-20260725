# タスク詳細取得API

## エンドポイント

```http
GET /checklists/{checklist_id}/tasks/{task_id}
```

## リクエスト

### パスパラメータ

| パラメータ | 型 | 必須 | 説明 |
| --- | --- | --- | --- |
| `checklist_id` | integer | 必須 | タスクが紐づくチェックリストID |
| `task_id` | integer | 必須 | 取得対象のタスクID |

## 成功レスポンス

```http
HTTP/1.1 200 OK
Content-Type: application/json
```

```json
{
  "id": 1,
  "checklist_id": 1,
  "title": "月次仕訳データの確認",
  "summary": "当月分の仕訳データに入力漏れがないか確認します。",
  "estimated_hours": 2.0
}
```

## 主要フィールド

タスク詳細取得APIとタスク編集APIは、次の同じ基本スキーマを扱う。

| フィールド | 型 | 制約 | 説明 |
| --- | --- | --- | --- |
| `id` | integer | - | タスクID |
| `checklist_id` | integer | - | 紐づくチェックリストID |
| `title` | string | 1〜255文字 | タスクタイトル |
| `summary` | string | 1文字以上 | タスク本文 |
| `estimated_hours` | number | 0より大きい有限数 | 工数 |

## エラーレスポンス

### バリデーションエラー

```http
HTTP/1.1 422 Unprocessable Entity
```

`checklist_id` または `task_id` が整数として不正な場合に返す。

### 存在しないチェックリストまたはタスク

```http
HTTP/1.1 404 Not Found
Content-Type: application/json
```

```json
{
  "detail": "Checklist or task not found"
}
```

## 対象外

- タスクの作成、削除、AIによる一括登録
- チェックリストの作成、編集、削除
- Backlog課題の作成、更新、削除、双方向同期
- 認証・認可
- Web実装時のブラウザからFastAPIへの直接通信。ADR 0002に従い、Next.jsサーバー側を通信境界とする
