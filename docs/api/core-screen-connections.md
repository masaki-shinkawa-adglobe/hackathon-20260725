# 基本画面接続API

## 共通方針

ブラウザはFastAPIを直接呼ばず、Next.jsのServer ComponentまたはServer Actionを経由する。認証・認可は扱わない。入力不正は422、存在しないIDと親子関係不一致は404を返す。

## チェックリスト一覧

`GET /checklists` はチェックリストを更新日時の降順で返す。各要素は `id`、`name`、`description`、`task_count`、`created_at`、`updated_at` を含む。完了状態はモデルに存在しないため、完了済み項目数は返さない。

## チェックリスト詳細

`GET /checklists/{checklist_id}` は基本情報とタスク一覧を返す。タスクは作成順で、`id`、`checklist_id`、`title`、`summary`、`estimated_hours`、`priority` を含む。

## チェックリスト作成・更新・削除

`POST /checklists` は `name`、任意の `description`、任意の `backlog_project_key_or_url` を受け取り、201で作成済みデータを返す。`PATCH /checklists/{checklist_id}` は同じ項目を更新する。名前はtrim後1〜255文字、空白だけの説明とBacklogプロジェクト値はnullへ正規化する。Backlogプロジェクト値は非空白なら入力どおりに保持する。

`DELETE /checklists/{checklist_id}` はチェックリストと配下のローカルタスクを削除し、204を返す。Backlog上のデータへ削除要求を送らない。

## タスク詳細・更新

`GET /checklists/{checklist_id}/tasks/{task_id}` は対象チェックリスト名とタスクを返す。`PATCH /checklists/{checklist_id}/tasks/{task_id}` は `title`、任意の `summary`、`estimated_hours`、`priority` を更新する。

タイトルはtrim後1〜255文字、工数は0より大きい有限数、優先順位は `high`、`medium`、`low` のいずれかとする。既存・新規・AI生成タスクの既定優先順位は `medium` とする。

## Backlogプロジェクト設定

チェックリスト単位で任意の `backlog_project_key_or_url` を保持する。プロジェクトキーまたはURLを自由入力として保存・返却し、Backlog APIによる候補取得、形式検証、接続確認は行わない。

基本CRUDとは別のAPI・画面接続単位として実装する。アプリ共通のBacklog認証設定には依存しない。

## Web画面

- 一覧画面は名前、説明、総タスク数、更新日時を表示し、取得済みデータを名前または説明で部分一致検索する
- 新規作成成功時は作成済みチェックリスト詳細へ遷移する
- 詳細画面は基本情報とタスク一覧を表示し、編集、削除、タスク編集への導線を提供する
- 削除前に確認ダイアログを表示し、成功時は一覧へ遷移する
- 新規作成・編集画面は名前、説明、任意のBacklogプロジェクトキーまたはURLを保存する
- 詳細画面はBacklogプロジェクトキーまたはURL、未設定時は未設定状態を表示する
- タスク編集画面はタイトル、本文、工数、優先順位を取得・更新する

## 対象外

- AI一括登録画面の接続
- タスク手動登録API・モーダルの実装
- タスク完了状態、並び替え、削除
- Backlog APIによるプロジェクト候補取得・接続確認
- 認証・認可
- 障害時の再試行導線、入力保持、詳細なエラー通知
- モバイル・タブレット向け専用レイアウト
