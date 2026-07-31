# AIタスク一括登録API

## 概要

既存チェックリストに対して、利用者の自由記述または資料ファイルをGemini AIで複数タスクへ分解し、対象チェックリストに紐づくタスクとして一括登録する。

## エンドポイント

```http
POST /checklists/ai-bulk-tasks
Content-Type: multipart/form-data
```

## リクエスト（multipart/form-data）

| フィールド | 型 | 必須 | 制約 | 説明 |
| --- | --- | --- | --- | --- |
| `checklist_id` | integer | 必須 | 既存チェックリストID | タスクを登録する対象チェックリスト |
| `description` | string \| null | 条件付き必須 | 最大10,000文字 | タスク分解に使う自由記述または資料ファイルと併用する補足指示 |
| `file` | file | 条件付き必須 | 単一ファイル、10 MiB以下 | タスク分解に使う資料 |

`description` と `file` のどちらか一方は必須である。両方を同時に送ることもできる。対応形式はPDF、XLSX、CSV、TXTである。PDFはGeminiへ文書として渡し、XLSXは全ワークシートをCSV相当のテキストへ抽出して渡す。CSV/TXTはUTF-8（BOM可）に限る。

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

FastAPI/Pydantic標準のバリデーションエラー形式または `detail` 文字列を返す。例として、`checklist_id` 未指定、`description` が10,000文字を超える、`description` と `file` がどちらも未指定の場合に発生する。

### ファイル形式・内容エラー

- 非対応の拡張子またはMIME型の不一致は `415 Unsupported Media Type`
- 10 MiBを超えるファイルは `413 Payload Too Large`
- UTF-8ではないCSV/TXT、壊れたXLSX、multipartの必須項目不足は `422 Unprocessable Entity`

いずれの失敗時もタスクは永続化されない。

## cURL例

```bash
curl -X POST http://localhost:8000/checklists/ai-bulk-tasks \
  -F 'checklist_id=1' \
  -F 'description=月次決算の作業を、担当者が順番に実行できる粒度のタスクへ分解してください。'
```

```bash
curl -X POST http://localhost:8000/checklists/ai-bulk-tasks \
  -F 'checklist_id=1' \
  -F 'description=月次決算の作業を、以下Excelファイルを参考にタスク分解してください。' \
  -F 'file=@./monthly-close.xlsx;type=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
```

## フロントエンド実装メモ

- 本APIはチェックリストを新規作成しない。
- 画面側は既存チェックリストの `id` を `checklist_id` として送る。
- 実行ボタンは二重送信を避けるため、リクエスト中はdisabledにする。
- 成功時は返却された `tasks` を画面へ反映する。
- `502` と `503` はAI連携起因として利用者へ再試行可能なエラーとして表示する。
- リクエストは常に `multipart/form-data` で送る。
- `description` と `file` がどちらも空の場合は送信前にエラー表示する。

## 環境変数

| 変数 | 必須 | 説明 |
| --- | --- | --- |
| `GEMINI_API_KEY` | 必須 | Gemini APIキー |
| `GEMINI_MODEL` | 任意 | Geminiモデル名。未指定時は `gemini-3.6-flash` |
