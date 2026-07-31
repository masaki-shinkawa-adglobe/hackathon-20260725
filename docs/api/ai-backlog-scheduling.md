# AI日程計画付きBacklog一括登録API

## 概要

チェックリスト内で利用者が選択した未発行タスクを、指定期間と想定担当者数に基づいてGemini AIで日程計画する。利用者が計画を確認した後、各タスクを1件ずつBacklog課題として登録する。課題へ個別の開始日・期限日を設定することで、Backlog標準ガントチャートへ表示する。

AIによる計画と外部Backlogへの書き込みは分離する。計画結果はDBへ保存し、発行時はクライアントから計画本体を再送せず`plan_id`を指定する。

## 共通前提

- ブラウザからFastAPIまたはBacklog APIへ直接アクセスしない
- Backlog接続設定はアプリ共通設定、プロジェクト設定はチェックリスト単位の`backlog_project_key_or_url`を使用する
- Gemini設定は`GEMINI_API_KEY`と`GEMINI_MODEL`を使用する
- 1ローカルタスクを1Backlog課題として登録する
- Backlogの実ユーザーへ担当者を自動設定しない
- 認証・認可のないローカル環境の単一利用者を前提とする

## 計画作成

```http
POST /checklists/{checklist_id}/backlog-plans
Content-Type: application/json
```

```json
{
  &#34;task_ids&#34;: [1, 2, 3],
  &#34;start_date&#34;: &#34;2026-08-03&#34;,
  &#34;end_date&#34;: &#34;2026-08-21&#34;,
  &#34;expected_assignee_count&#34;: 2
}
```

| フィールド | 型 | 必須 | 制約 |
| --- | --- | --- | --- |
| `task_ids` | integer[] | 必須 | 1件以上、重複不可、対象チェックリストの未発行タスクだけ |
| `start_date` | string | 必須 | `YYYY-MM-DD` |
| `end_date` | string | 必須 | `YYYY-MM-DD`、開始日以降 |
| `expected_assignee_count` | integer | 必須 | 1以上 |

### 計画ルール

- 1人1日8時間とする
- 土日は非稼働日とし、祝日は考慮しない
- 1タスクは匿名の担当枠1つを連続して占有する
- 1タスクの所要営業日数は`ceil(estimated_hours / 8)`とする
- 同時稼働する担当枠数は`expected_assignee_count`以下とする
- AIは選択タスクのタイトル、本文、工数から依存関係、担当枠、開始日、期限日を決める
- AIはタスクの追加・削除・分割・統合、タイトル・本文・工数の変更を行わない
- 後続タスクは先行タスクの期限日の次の営業日以降に開始する
- すべてのタスクを指定期間内へ配置する

サーバーは、選択タスクが過不足なく1回ずつ含まれること、担当枠の範囲、同一担当枠内の日程重複、所要営業日数、期間内配置、依存順序、依存関係の循環を検証する。Gemini応答が制約違反の場合は自動再生成せず、計画を保存しない。

### 成功レスポンス

```http
HTTP/1.1 201 Created
```

```json
{
  &#34;plan_id&#34;: 10,
  &#34;checklist_id&#34;: 1,
  &#34;status&#34;: &#34;planned&#34;,
  &#34;start_date&#34;: &#34;2026-08-03&#34;,
  &#34;end_date&#34;: &#34;2026-08-21&#34;,
  &#34;expected_assignee_count&#34;: 2,
  &#34;items&#34;: [
    {
      &#34;task_id&#34;: 1,
      &#34;title&#34;: &#34;要件を確認する&#34;,
      &#34;estimated_hours&#34;: 8,
      &#34;assignee_slot&#34;: 1,
      &#34;start_date&#34;: &#34;2026-08-03&#34;,
      &#34;due_date&#34;: &#34;2026-08-03&#34;,
      &#34;depends_on_task_ids&#34;: []
    },
    {
      &#34;task_id&#34;: 2,
      &#34;title&#34;: &#34;実装する&#34;,
      &#34;estimated_hours&#34;: 16,
      &#34;assignee_slot&#34;: 1,
      &#34;start_date&#34;: &#34;2026-08-04&#34;,
      &#34;due_date&#34;: &#34;2026-08-05&#34;,
      &#34;depends_on_task_ids&#34;: [1]
    }
  ]
}
```

計画は期限切れにしない。不要計画の削除は本APIの対象外とする。計画確認後に対象タスク、期間、担当者数を変更する場合は既存計画を編集せず、新しい計画を作成する。

## Backlog発行

```http
POST /checklists/{checklist_id}/backlog-plans/{plan_id}/issues
```

リクエストボディは使用しない。DBへ保存済みの計画だけを発行対象とする。発行前に以下を検証する。

- 計画が対象チェックリストに属する
- 計画対象タスクのタイトル、本文、工数が計画時点から変更されていない
- 対象タスクが削除されていない
- チェックリストのBacklogプロジェクト設定が計画時点と一致する
- Backlog接続設定が利用可能である
- 対象プロジェクトの`chartEnabled`が`true`である
- 対象タスクに発行済み紐づきがない

発行時はBacklogのプロジェクト情報、課題種別一覧、優先度一覧を取得する。課題種別は表示順先頭、優先度は`Normal`を使用する。各課題にはローカルタスクのタイトル、本文、工数と、計画済みの開始日・期限日を設定する。`assigneeId`は設定しない。

### 成功・部分成功レスポンス

全件成功または発行済み項目だけの場合は`200 OK`、一部失敗は`207 Multi-Status`を返す。

```json
{
  &#34;plan_id&#34;: 10,
  &#34;status&#34;: &#34;partial&#34;,
  &#34;gantt_url&#34;: &#34;https://example.backlog.com/gantt/DEMO&#34;,
  &#34;issued&#34;: [
    {
      &#34;task_id&#34;: 1,
      &#34;backlog_issue_id&#34;: 101,
      &#34;backlog_issue_key&#34;: &#34;DEMO-1&#34;,
      &#34;backlog_issue_url&#34;: &#34;https://example.backlog.com/view/DEMO-1&#34;,
      &#34;start_date&#34;: &#34;2026-08-03&#34;,
      &#34;due_date&#34;: &#34;2026-08-03&#34;
    }
  ],
  &#34;already_issued&#34;: [],
  &#34;failed&#34;: [
    {
      &#34;task_id&#34;: 2,
      &#34;code&#34;: &#34;backlog_request_failed&#34;,
      &#34;message&#34;: &#34;Backlog課題の登録に失敗しました&#34;,
      &#34;retryable&#34;: true
    }
  ]
}
```

各課題の作成成功直後にタスク単位の紐づきを短いDBトランザクションで保存する。同じ`plan_id`を再実行した場合、成功済みタスクは再発行せず、未発行分だけ処理する。Backlog課題の自動削除や全件ロールバックは行わない。

## 計画状態

| 状態 | 説明 |
| --- | --- |
| `planned` | 計画済み、未発行 |
| `partial` | 一部発行成功、未発行項目あり |
| `issued` | 全項目が発行済み |

## エラー

| HTTP | code | 条件 |
| --- | --- | --- |
| `404` | `checklist_not_found` | チェックリストなし |
| `404` | `plan_not_found` | 計画なしまたは親子関係不一致 |
| `422` | `invalid_input` | 日付、担当者数、タスクID不正 |
| `422` | `schedule_impossible` | 指定期間・担当者数では計画不能 |
| `422` | `gantt_disabled` | Backlogプロジェクトのガント機能が無効 |
| `409` | `task_already_issued` | 計画対象に発行済みタスクを含む |
| `409` | `stale_plan` | タスク内容またはプロジェクト設定が計画時から変更済み |
| `502` | `invalid_ai_schedule` | Gemini応答が不正または制約違反 |
| `502` | `gemini_request_failed` | Gemini呼び出し失敗 |
| `502` | `backlog_request_failed` | Backlog呼び出し失敗 |
| `503` | `integration_not_configured` | GeminiまたはBacklog設定不足 |

エラー応答とログへAPIキーなどの秘密情報を含めない。Gemini計画の自動再生成とBacklog通信の無制限再試行は行わない。

## DB責務

- 計画条件と状態を保持する計画テーブル
- タスクのスナップショット、担当枠、日付、依存タスクIDを保持する計画項目テーブル
- タスクIDを一意とし、Backlog課題ID・キー・URL・発行日時を保持するタスクBacklog紐づきテーブル
- 現行のチェックリスト単位課題紐づきテーブルは廃止し、既存行は移行しない
- チェックリスト一覧・詳細のBacklog登録状態は、配下タスクの紐づきを集計して返す

## 対象外

- アプリ内ガントチャート描画
- 計画結果の日付・担当枠・依存関係の手動編集
- Backlog実ユーザーへの担当者割り当て
- 祝日、個人別稼働率、休暇、1タスクの複数人並行作業
- 計画の削除・期限切れ・定期クリーンアップ
- Backlog課題の更新・削除・双方向同期
- 認証・認可
