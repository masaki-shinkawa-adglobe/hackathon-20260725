# Issue Agents

## Issue実装フロー

```text
利用者
  → Issue Orchestrator
    → Issue Planner
    → Issue Implementer
    → Issue Reviewer
```

- Orchestratorは1件のIssueを受け取り、ほかの3役を順番に呼び出します。
- Plannerは実装計画だけを作成します。
- Implementerは計画に沿って実装とテストを行います。
- Reviewerは変更を編集せずにレビューします。

## 要件整理

`issue-requirements-interviewer`は、新しい要件を整理して実装前のIssueを作成する独立Skillです。Issue実装フローからは呼び出しません。
