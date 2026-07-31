# チェックリスト作成API

## エンドポイント

```http
POST /checklists
Content-Type: application/json
```

## リクエスト

```json
{
  "name": "月次決算業務",
  "description": "月次決算の標準チェックリスト",
  "backlog_project_key_or_url": "PROJ"
}
```

| フィールド | 型 | 必須 | 制約 | 説明 |
| --- | --- | --- | --- | --- |
| `name` | string | 必須 | 1〜255文字、空白のみ不可 | チェックリスト名 |
| `description` | string \| null | 任意 | 空文字列を許容 | チェックリストの説明 |
| `backlog_project_key_or_url` | string \| null | 任意 | 自由入力 | BacklogのプロジェクトキーまたはURL |

## 成功レスポンス

```http
HTTP/1.1 201 Created
Content-Type: application/json
```

```json
{
  "id": 1,
  "name": "月次決算業務",
  "description": "月次決算の標準チェックリスト",
  "backlog_project_key_or_url": "PROJ"
}
```

## 主要フィールド

| フィールド | 型 | 説明 |
| --- | --- | --- |
| `id` | integer | 作成されたチェックリストID |
| `name` | string | 作成されたチェックリスト名 |
| `description` | string \| null | 作成されたチェックリストの説明 |
| `backlog_project_key_or_url` | string \| null | 入力されたBacklogのプロジェクトキーまたはURL |

## エラーレスポンス

### バリデーションエラー

```http
HTTP/1.1 422 Unprocessable Entity
```

`name` の未指定・空文字列・空白のみ・256文字以上など、リクエストが制約を満たさない場合に返す。

## 対象外

- タスクの作成、編集、削除
- Backlog課題の作成、更新、削除、双方向同期
- 認証・認可
- Web実装時のブラウザからFastAPIへの直接通信。ADR 0002に従い、Next.jsサーバー側を通信境界とする
