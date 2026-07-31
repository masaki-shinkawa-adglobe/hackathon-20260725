# AIタスク一括登録API

## 概要

既存チェックリストに対して、利用者の自由記述をGemini AIで複数タスクへ分解し、対象チェックリストに紐づくタスクとして一括登録する。

ファイルアップロードは本APIの対象外とし、別Issueで扱う。

## エンドポイント

```http
POST /checklists/ai-bulk-tasks
Content-Type: application/json
```

## リクエスト

| フィールド | 型 | 必須 | 制約 | 説明 |
| --- | --- | --- | --- | --- |
| `checklist_id` | integer | 必須 | 既存チェックリストID | タスクを登録する対象チェックリスト |
| `description` | string \| null | 任意 | 最大10,000文字 | タスク分解に使う自由記述 |

```json
{
  "checklist_id": 1,
  "description": "月次決算の作業を、担当者が順番に実行できる粒度のタスクへ分解してください。"
}
```

`description` は省略できる。

```json
{
  "checklist_id": 1
}
```

## 成功レスポンス

```http
HTTP/1.1 200 OK
Content-Type: application/json
```

```json
{
  "checklist": {
    "id": 1,
    "name": "月次決算業務",
    "description": "月次決算の標準チェックリスト"
  },
  "tasks": [
    {
      "id": 1,
      "checklist_id": 1,
      "title": "月次仕訳データの確認",
      "summary": "当月分として計上された仕訳データに入力漏れや不適切な勘定科目の使用がないか確認します。",
      "estimated_hours": 2.0
    },
    {
      "id": 2,
      "checklist_id": 1,
      "title": "月次試算表の作成",
      "summary": "仕訳と残高の確認完了後、当期の月次試算表を出力して作成します。",
      "estimated_hours": 1.0
    }
  ]
}
```

| フィールド | 型 | 説明 |
| --- | --- | --- |
| `checklist.id` | integer | 対象チェックリストID |
| `checklist.name` | string | 対象チェックリスト名 |
| `checklist.description` | string \| null | 対象チェックリスト説明 |
| `tasks[].id` | integer | 作成されたタスクID |
| `tasks[].checklist_id` | integer | 紐づくチェックリストID |
| `tasks[].title` | string | タスクタイトル |
| `tasks[].summary` | string | タスク概要 |
| `tasks[].estimated_hours` | number | 見積工数。0より大きい有限数 |

成功時、レスポンスに含まれる `tasks` はDBへ永続化済み。

## エラーレスポンス

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

### Gemini APIキー未設定

```http
HTTP/1.1 503 Service Unavailable
Content-Type: application/json
```

```json
{
  "detail": {
    "code": "gemini_not_configured",
    "message": "GEMINI_API_KEY is not configured"
  }
}
```

### Gemini API呼び出し失敗

```http
HTTP/1.1 502 Bad Gateway
Content-Type: application/json
```

```json
{
  "detail": {
    "code": "gemini_request_failed",
    "message": "Gemini API request failed"
  }
}
```

### Gemini応答不正

```http
HTTP/1.1 502 Bad Gateway
Content-Type: application/json
```

```json
{
  "detail": {
    "code": "invalid_ai_response",
    "message": "Gemini returned an invalid task list"
  }
}
```

空配列、JSONとして不正、必須フィールド不足、`estimated_hours` が0以下・無限大・NaNの場合はこのエラーになる。

### バリデーションエラー

```http
HTTP/1.1 422 Unprocessable Entity
Content-Type: application/json
```

FastAPI/Pydantic標準のバリデーションエラー形式を返す。例として、`checklist_id` 未指定、`description` が10,000文字を超える場合に発生する。

## cURL例

```bash
curl -X POST http://localhost:8000/checklists/ai-bulk-tasks \
  -H 'Content-Type: application/json' \
  -d '{
    "checklist_id": 1,
    "description": "月次決算の作業を、担当者が順番に実行できる粒度のタスクへ分解してください。"
  }'
```

## フロントエンド実装メモ

- 本APIはチェックリストを新規作成しない。
- 画面側は既存チェックリストの `id` を `checklist_id` として送る。
- 実行ボタンは二重送信を避けるため、リクエスト中はdisabledにする。
- 成功時は返却された `tasks` を画面へ反映する。
- `502` と `503` はAI連携起因として利用者へ再試行可能なエラーとして表示する。
- ファイルアップロードでの一括登録は別APIとして設計する。

## 環境変数

| 変数 | 必須 | 説明 |
| --- | --- | --- |
| `GEMINI_API_KEY` | 必須 | Gemini APIキー |
| `GEMINI_MODEL` | 任意 | Geminiモデル名。未指定時は `gemini-3.6-flash` |
