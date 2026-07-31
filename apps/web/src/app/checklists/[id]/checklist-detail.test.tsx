import { cleanup, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, expect, test, vi } from "vitest"

import { ChecklistDetail } from "./checklist-detail"

const toastMock = vi.hoisted(() => ({
  success: vi.fn(),
  warning: vi.fn(),
}))

vi.mock("sonner", () => ({ toast: toastMock }))

function checklistResponse({ id = 1, name = "チェックリスト", tasks = [] }: Partial<{ id: number; name: string; tasks: unknown[] }> = {}) {
  return new Response(JSON.stringify({ id, name, description: null, tasks }), { status: 200 })
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  toastMock.success.mockReset()
  toastMock.warning.mockReset()
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
  expect(screen.getByRole("link", { name: "仕訳を確認" })).toHaveAttribute(
    "href",
    "/checklists/1/tasks/10"
  )
  expect(screen.getByRole("cell", { name: "当月の仕訳を確認します。" })).toBeInTheDocument()
  expect(screen.getByRole("cell", { name: "2時間" })).toBeInTheDocument()
  expect(screen.getByRole("cell", { name: "1.5時間" })).toBeInTheDocument()
  expect(screen.getByRole("link", { name: "チェックリスト一覧へ戻る" })).toHaveAttribute("href", "/")
  expect(screen.getByRole("link", { name: "編集する" })).toHaveAttribute("href", "/checklists/1/edit")
})

test("タスクが0件の場合は空状態を表示する", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: 1, name: "空のリスト", description: null, tasks: [] }), { status: 200 })))

  render(<ChecklistDetail checklistId="1" />)

  expect(await screen.findByText("タスクはまだ登録されていません")).toBeInTheDocument()
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

test("AI一括登録モーダルを実チェックリストIDで開く", async () => {
  const fetchMock = vi.fn().mockResolvedValue(checklistResponse({ id: 42, name: "実IDのリスト" }))
  vi.stubGlobal("fetch", fetchMock)
  const user = userEvent.setup()

  render(<ChecklistDetail checklistId="slug" />)

  await screen.findByRole("heading", { name: "実IDのリスト" })
  await user.click(screen.getByRole("button", { name: "AIでタスクを一括登録" }))
  await user.type(screen.getByLabelText("説明（任意）"), "タスクを作成する")
  await user.click(screen.getByRole("button", { name: "AIで登録" }))

  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
  expect(fetchMock.mock.calls[1][0]).toBe("/api/checklists/ai-bulk-tasks")
  expect((fetchMock.mock.calls[1][1] as RequestInit).body).toBeInstanceOf(FormData)
  expect(((fetchMock.mock.calls[1][1] as RequestInit).body as FormData).get("checklist_id")).toBe("42")
})

test("AI登録成功後に詳細を再取得して一覧を更新し、作成件数を通知する", async () => {
  const fetchMock = vi.fn()
    .mockResolvedValueOnce(checklistResponse({ id: 1, tasks: [] }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ tasks: [
      { id: 10, checklist_id: 1, title: "確認する", summary: "内容を確認", estimated_hours: 1 },
      { id: 11, checklist_id: 1, title: "共有する", summary: "結果を共有", estimated_hours: 0.5 },
    ] }), { status: 200 }))
    .mockResolvedValueOnce(checklistResponse({ id: 1, tasks: [
      { id: 10, checklist_id: 1, title: "確認する", summary: "内容を確認", estimated_hours: 1 },
      { id: 11, checklist_id: 1, title: "共有する", summary: "結果を共有", estimated_hours: 0.5 },
    ] }))
  vi.stubGlobal("fetch", fetchMock)
  const user = userEvent.setup()

  render(<ChecklistDetail checklistId="1" />)

  await screen.findByRole("heading", { name: "チェックリスト" })
  await user.click(screen.getByRole("button", { name: "AIでタスクを一括登録" }))
  await user.type(screen.getByLabelText("説明（任意）"), "タスクを作成する")
  await user.click(screen.getByRole("button", { name: "AIで登録" }))

  expect(await screen.findByRole("link", { name: "確認する" })).toBeInTheDocument()
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3))
  expect(fetchMock.mock.calls[2][0]).toBe("/api/checklists/1")
  expect(toastMock.success).toHaveBeenCalledWith("2件のタスクを登録しました")
})

test("AI登録後の詳細再取得に失敗しても登録成功を維持して警告する", async () => {
  const fetchMock = vi.fn()
    .mockResolvedValueOnce(checklistResponse({ id: 1, tasks: [] }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ tasks: [
      { id: 10, checklist_id: 1, title: "確認する", summary: "内容を確認", estimated_hours: 1 },
    ] }), { status: 200 }))
    .mockRejectedValueOnce(new Error("network error"))
  vi.stubGlobal("fetch", fetchMock)
  const user = userEvent.setup()

  render(<ChecklistDetail checklistId="1" />)

  await screen.findByRole("heading", { name: "チェックリスト" })
  await user.click(screen.getByRole("button", { name: "AIでタスクを一括登録" }))
  await user.type(screen.getByLabelText("説明（任意）"), "タスクを作成する")
  await user.click(screen.getByRole("button", { name: "AIで登録" }))

  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3))
  expect(toastMock.success).toHaveBeenCalledWith("1件のタスクを登録しました")
  expect(toastMock.warning).toHaveBeenCalledWith("登録は完了しましたが、一覧を更新できませんでした。画面を再読み込みしてください")
  expect(screen.queryByRole("alert")).not.toBeInTheDocument()
  expect(screen.queryByText("再試行")).not.toBeInTheDocument()
})
