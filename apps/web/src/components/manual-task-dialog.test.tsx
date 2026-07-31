import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { useState } from "react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ManualTaskDialog } from "./manual-task-dialog"

const toast = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn() }))
vi.mock("sonner", () => ({ toast }))

const onSuccess = vi.fn().mockResolvedValue(true)

function DialogHarness() {
  const [open, setOpen] = useState(false)
  return <ManualTaskDialog checklistId={12} open={open} onOpenChange={setOpen} onSuccess={onSuccess} trigger={<button type="button">タスク手動登録</button>} />
}

function fillRequiredFields() {
  fireEvent.change(screen.getByLabelText("タイトル"), { target: { value: "  仕訳を確認  " } })
  fireEvent.change(screen.getByLabelText("工数（時間）"), { target: { value: "1.5" } })
}

describe("ManualTaskDialog", () => {
  afterEach(() => {
    cleanup()
    onSuccess.mockClear()
    toast.success.mockClear()
    toast.error.mockClear()
    vi.unstubAllGlobals()
  })

  it("トリガーで開き、初期フォーカスとキャンセル後のフォーカス復帰を提供する", async () => {
    render(<DialogHarness />)
    const trigger = screen.getByRole("button", { name: "タスク手動登録" })
    fireEvent.click(trigger)

    expect(screen.getByRole("dialog")).toBeInTheDocument()
    await waitFor(() => expect(screen.getByLabelText("タイトル")).toHaveFocus())
    fireEvent.click(screen.getByRole("button", { name: "キャンセル" }))
    await waitFor(() => expect(trigger).toHaveFocus())
  })

  it("タイトルと工数を検証し、項目の直下に支援技術向けエラーを表示する", () => {
    render(<DialogHarness />)
    fireEvent.click(screen.getByRole("button", { name: "タスク手動登録" }))
    fireEvent.click(screen.getByRole("button", { name: "登録する" }))

    const title = screen.getByLabelText("タイトル")
    const estimatedHours = screen.getByLabelText("工数（時間）")
    expect(title).toHaveAttribute("aria-describedby", "manual-task-title-error")
    expect(estimatedHours).toHaveAttribute("aria-describedby", "manual-task-estimated-hours-error")
    expect(screen.getByText("タイトルは1〜255文字で入力してください。")).toBeInTheDocument()
    expect(screen.getByText("工数は0より大きい数値で入力してください。")).toBeInTheDocument()

    fireEvent.change(title, { target: { value: "x".repeat(256) } })
    fireEvent.change(estimatedHours, { target: { value: "0" } })
    fireEvent.click(screen.getByRole("button", { name: "登録する" }))
    expect(screen.getAllByRole("alert")).toHaveLength(2)
  })

  it("正規化したJSONを送信し、再取得完了後に閉じて成功Toastを表示する", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: 4, checklist_id: 12, title: "仕訳を確認", summary: null, estimated_hours: 1.5 }), { status: 201 }))
    vi.stubGlobal("fetch", fetchMock)
    render(<DialogHarness />)
    fireEvent.click(screen.getByRole("button", { name: "タスク手動登録" }))
    fillRequiredFields()
    fireEvent.change(screen.getByLabelText("本文（任意）"), { target: { value: "   " } })
    fireEvent.click(screen.getByRole("button", { name: "登録する" }))

    await waitFor(() => expect(onSuccess).toHaveBeenCalledTimes(1))
    expect(fetchMock).toHaveBeenCalledWith("/api/checklists/12/tasks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: "仕訳を確認", summary: null, estimated_hours: 1.5 }),
    })
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument())
    expect(toast.success).toHaveBeenCalledWith("タスクを登録しました。")

    fireEvent.click(screen.getByRole("button", { name: "タスク手動登録" }))
    expect(screen.getByLabelText("タイトル")).toHaveValue("")
    expect(screen.getByLabelText("本文（任意）")).toHaveValue("")
    expect(screen.getByLabelText("工数（時間）")).toHaveValue(null)
  })

  it("送信中は全操作による閉鎖と入力を無効化する", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(() => {})))
    render(<DialogHarness />)
    fireEvent.click(screen.getByRole("button", { name: "タスク手動登録" }))
    fillRequiredFields()
    fireEvent.click(screen.getByRole("button", { name: "登録する" }))

    expect(screen.getByLabelText("タイトル")).toBeDisabled()
    expect(screen.getByLabelText("本文（任意）")).toBeDisabled()
    expect(screen.getByLabelText("工数（時間）")).toBeDisabled()
    expect(screen.getByRole("button", { name: "キャンセル" })).toBeDisabled()
    expect(screen.getByRole("button", { name: "登録中…" })).toBeDisabled()
    const dialog = screen.getByRole("dialog")
    fireEvent.keyDown(dialog, { key: "Escape" })
    fireEvent.pointerDown(document.querySelector('[data-slot="dialog-overlay"]') as Element)
    expect(screen.getByRole("dialog")).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Close" })).not.toBeInTheDocument()
  })

  it("APIエラー時は入力を保持し、エラーToastを表示して再試行できる", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ code: "upstream_error" }), { status: 502 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: 4, checklist_id: 12, title: "確認", summary: "本文", estimated_hours: 1 }), { status: 201 }))
    vi.stubGlobal("fetch", fetchMock)
    render(<DialogHarness />)
    fireEvent.click(screen.getByRole("button", { name: "タスク手動登録" }))
    fillRequiredFields()
    fireEvent.change(screen.getByLabelText("本文（任意）"), { target: { value: "保持する本文" } })
    fireEvent.click(screen.getByRole("button", { name: "登録する" }))

    await waitFor(() => expect(toast.error).toHaveBeenCalled())
    expect(screen.getByLabelText("タイトル")).toHaveValue("  仕訳を確認  ")
    expect(screen.getByLabelText("本文（任意）")).toHaveValue("保持する本文")
    fireEvent.click(screen.getByRole("button", { name: "登録する" }))
    await waitFor(() => expect(onSuccess).toHaveBeenCalledTimes(1))
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })
})
