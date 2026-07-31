# チェックリスト削除API

## エンドポイント

```http
DELETE /checklists/{checklist_id}
```

## リクエスト

### パスパラメータ

| パラメータ | 型 | 必須 | 説明 |
| --- | --- | --- | --- |
| `checklist_id` | integer | 必須 | 削除対象のチェックリストID |

対象のチェックリストと、それに紐づくすべてのタスクを削除する。Backlog上の課題は削除しない。

## 成功レスポンス

```http
HTTP/1.1 204 No Content
```

成功時のレスポンス本文は返さない。

## エラーレスポンス

### バリデーションエラー

```http
HTTP/1.1 422 Unprocessable Entity
```

`checklist_id` が整数として不正な場合に返す。

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

- Backlog上の課題の削除、およびBacklog課題の作成、更新、双方向同期
- タスク単位の削除API
- 認証・認可
- Web実装時のブラウザからFastAPIへの直接通信。ADR 0002に従い、Next.jsサーバー側を通信境界とする
