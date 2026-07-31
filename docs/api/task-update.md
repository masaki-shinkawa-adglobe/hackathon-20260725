# タスク編集API

## エンドポイント

```http
PATCH /checklists/{checklist_id}/tasks/{task_id}
Content-Type: application/json
```

## リクエスト

### パスパラメータ

| パラメータ | 型 | 必須 | 説明 |
| --- | --- | --- | --- |
| `checklist_id` | integer | 必須 | タスクが紐づくチェックリストID |
| `task_id` | integer | 必須 | 編集対象のタスクID |

```json
{
  "title": "月次仕訳データの確認",
  "summary": "当月分の仕訳データに入力漏れがないか確認します。",
  "estimated_hours": 2.5,
  "priority": "high"
}
```

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
  "estimated_hours": 2.5,
  "priority": "high"
}
```

## 主要フィールド

タスク詳細取得APIとタスク編集APIは、次の同じ基本スキーマを扱う。

| フィールド | 型 | 制約 | 説明 |
| --- | --- | --- | --- |
| `id` | integer | - | タスクID |
| `checklist_id` | integer | - | 紐づくチェックリストID |
| `title` | string | 1〜255文字 | タスクタイトル |
| `summary` | string \| null | - | タスク本文 |
| `estimated_hours` | number | 0より大きい有限数 | 工数 |
| `priority` | `high` \| `medium` \| `low` | - | 優先順位（高・中・低） |

リクエストでは `title`、`summary`、`estimated_hours`、`priority` をすべて必須とする。`title`はtrim後1〜255文字、空白のみの`summary`は`null`へ正規化する。`id` と `checklist_id` はパスパラメータで対象を指定し、成功レスポンスで返す。

## エラーレスポンス

### バリデーションエラー

```http
HTTP/1.1 422 Unprocessable Entity
```

`checklist_id`、`task_id`、`title`、`summary`、`estimated_hours` が制約を満たさない場合に返す。

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
