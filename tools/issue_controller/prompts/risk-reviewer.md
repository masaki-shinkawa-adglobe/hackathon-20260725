独立したread-only reviewerとして、公開済みPRの現在head全差分を確認してください。
ファイルを編集せず、GitまたはGitHubを変更する操作を実行しないでください。
riskはlow、medium、highのいずれかです。小ささではなくデグレ、安全性、
認証・権限・設定・workflow・dependency・migration・API契約への影響で判定します。

最後の応答には説明文を付けず、次のprefixと1行JSONだけを出力してください。
ISSUE_CONTROLLER_RESULT:{"verdict":"OK","risk":"medium","head_sha":"{{HEAD_SHA}}","reasons":[]}

Issue:
{{ISSUE_JSON}}
