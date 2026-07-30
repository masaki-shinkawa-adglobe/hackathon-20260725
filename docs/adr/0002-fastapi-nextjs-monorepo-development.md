# FastAPI・Next.jsモノレポのローカル開発構成

## 状況

採用

## 背景

既存リポジトリにはPython製Issue Controllerがあり、新たにNext.jsフロントエンド、FastAPIバックエンド、PostgreSQLを追加する。従来のNext.jsルート直下配置では、既存Python packageとの境界が曖昧になり、フロントエンドとバックエンドの依存管理やDocker build contextが衝突しやすい。

ローカル開発では、複数ランタイムとDBの起動順、マイグレーション、ホットリロードを再現可能にする必要がある。一方、初期構築に本番運用や業務機能を含めると、環境基盤の責務を越える。

## 決定

- Next.jsを`apps/web`、FastAPIを`apps/api`へ配置する。
- JavaScript依存関係はルートのpnpm workspace、Python依存関係は`apps/api`内のuv projectとlockfileで分離する。
- ローカル開発はDocker Composeを正規の起動方法とし、`web`、`api`、`migrate`、`db`サービスを定義する。
- PostgreSQLはホストへポート公開せず、名前付きVolumeへ永続化する。
- `db`のhealthy後にAlembicの一回限りの`migrate`サービスを実行し、成功後にFastAPIを起動する。
- FastAPIはSQLAlchemy 2.xの非同期ORMとasyncpgを使用し、DB処理単位で短い`AsyncSession`を作成する。
- Next.jsはApp Routerを使用し、Server ComponentからCompose内部のFastAPIへアクセスする。ブラウザからFastAPIへ直接アクセスしない。
- `.env.local`にはコミット可能なローカル設定だけを置き、秘密情報はGit管理しない`.env`へ分離する。

## 結果

- フロントエンド、バックエンド、既存Issue Controllerの依存関係と配置境界が明確になる。
- 一つのComposeコマンドで起動順と開発時の自動反映を再現できる。
- DBはホストから直接接続できないため、手動操作には`docker compose exec db psql`などを使用する。
- 外部APIを挟む処理では単一の長時間トランザクションを使えないため、短いDB処理と状態管理・冪等性を組み合わせる。
- 自動テスト、CI、本番デプロイ、認証・認可、業務テーブルは後続の要件とIssueで扱う。
