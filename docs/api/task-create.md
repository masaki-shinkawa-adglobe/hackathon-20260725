# 手動タスク作成API

## 概要

既存チェックリストへ、利用者が入力したタスクを1件追加する。

## エンドポイント

```http
POST /checklists/{checklist_id}/tasks
Content-Type: application/json
```

## リクエスト

```json
{
  "title": "請求書の照合",
  "summary": "請求書と発注内容を照合する。",
  "estimated_hours": 2
}
```

| フィールド | 型 | 必須 | 制約 |
| --- | --- | --- | --- |
| `title` | string | 必須 | trim後1〜255文字 |
| `summary` | string \| null | 任意 | 未入力または空白のみは`null`へ正規化。文字数上限なし |
| `estimated_hours` | number | 必須 | 0より大きい有限数。小数可 |

画面の「タイトル」は`tasks.title`、「本文」は`tasks.summary`、「工数」は`tasks.estimated_hours`へ保存する。

## 成功レスポンス

```http
HTTP/1.1 201 Created
Content-Type: application/json
```

```json
{
  "id": 10,
  "checklist_id": 1,
  "title": "請求書の照合",
  "summary": "請求書と発注内容を照合する。",
  "estimated_hours": 2
}
```

成功レスポンスはDBへ永続化済みのタスクを返す。

## エラーレスポンス

### 対象チェックリストなし

存在しない`checklist_id`は`404 Not Found`とする。

```json
{
  "detail": "Checklist not found"
}
```

### 入力不正

タイトル未入力・空白のみ・255文字超過、工数が0以下・無限大・NaNの場合は`422 Unprocessable Entity`とする。

入力検証または永続化に失敗した場合、タスクを作成しない。

## 対象外

- タスクの優先順位、表示順、削除、完了状態、担当者
- タスク詳細取得・更新・並び替えAPI
- AIによるタスク一括登録
- 認証・認可
