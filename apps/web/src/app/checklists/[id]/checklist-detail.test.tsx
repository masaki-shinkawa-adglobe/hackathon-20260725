import { cleanup, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, expect, test, vi } from "vitest"

import { ChecklistDetail } from "./checklist-detail"

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

test("実API形式のチェックリストとタスクを表示する", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
    id: 1,
    name: "月次決算",
    description: "月ごとの締め作業です。",
    backlog_registration: { is_registered: false, link_id: null, backlog_issue_id: null, backlog_issue_key: null, backlog_issue_url: null },
    tasks: [
      { id: 10, checklist_id: 1, title: "仕訳を確認", summary: "当月の仕訳を確認します。", estimated_hours: 2 },
      { id: 11, checklist_id: 1, title: "試算表を作成", summary: "試算表を出力します。", estimated_hours: 1.5 },
    ],
  }), { status: 200 })))

  render(<ChecklistDetail checklistId="1" />)

  expect(await screen.findByRole("heading", { name: "月次決算" })).toBeInTheDocument()
  expect(screen.getByText("月ごとの締め作業です。")).toBeInTheDocument()
  expect(screen.getByRole("columnheader", { name: "タイトル" })).toBeInTheDocument()
  expect(screen.getByRole("cell", { name: "仕訳を確認" })).toBeInTheDocument()
  expect(screen.getByRole("cell", { name: "当月の仕訳を確認します。" })).toBeInTheDocument()
  expect(screen.getByRole("cell", { name: "2時間" })).toBeInTheDocument()
  expect(screen.getByRole("cell", { name: "1.5時間" })).toBeInTheDocument()
  expect(screen.getByRole("link", { name: "一覧へ戻る" })).toHaveAttribute("href", "/")
  expect(screen.getByRole("link", { name: "編集" })).toHaveAttribute("href", "/checklists/1/edit")
})

test("タスクが0件の場合は空状態を表示する", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: 1, name: "空のリスト", description: null, tasks: [] }), { status: 200 })))

  render(<ChecklistDetail checklistId="1" />)

  expect(await screen.findByText("登録されているタスクはありません。")).toBeInTheDocument()
  expect(screen.getByText("説明はありません。")).toBeInTheDocument()
  expect(screen.queryByRole("table")).not.toBeInTheDocument()
})

test("取得失敗後に再試行して表示を復旧する", async () => {
  const fetchMock = vi.fn()
    .mockRejectedValueOnce(new Error("network error"))
    .mockResolvedValueOnce(new Response(JSON.stringify({ id: 1, name: "復旧済み", description: null, tasks: [] }), { status: 200 }))
  vi.stubGlobal("fetch", fetchMock)
  const user = userEvent.setup()

  render(<ChecklistDetail checklistId="1" />)

  expect(await screen.findByRole("alert")).toHaveTextContent("チェックリストを取得できませんでした")
  await user.click(screen.getByRole("button", { name: "再試行" }))
  expect(await screen.findByRole("heading", { name: "復旧済み" })).toBeInTheDocument()
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
})
