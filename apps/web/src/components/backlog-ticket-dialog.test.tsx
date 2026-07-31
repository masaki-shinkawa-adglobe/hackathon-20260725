import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { useState } from "react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { BacklogTicketDialog, type BacklogTicketDialogSubmitValues } from "./backlog-ticket-dialog"

const tasks = [
  { id: "task-1", title: "要件を確認する" },
  { id: "task-2", title: "実装する" },
  { id: "task-3", title: "テストする" },
]
const onClose = vi.fn()
const onSubmit = vi.fn<(values: BacklogTicketDialogSubmitValues) => void>()

function DialogHarness() {
  const [open, setOpen] = useState(true)
  return <><button type="button" onClick={() => setOpen(true)}>開く</button><BacklogTicketDialog tasks={tasks} initialStartDate="2025-06-01" initialEndDate="2025-06-30" initialExpectedAssigneeCount={3} initialSelectedTaskIds={["task-1", "task-2"]} open={open} onClose={() => { onClose(); setOpen(false) }} onSubmit={onSubmit} /></>
}

describe("BacklogTicketDialog", () => {
  afterEach(() => { cleanup(); onClose.mockReset(); onSubmit.mockReset() })

  it("日付の必須・前後関係を表示し、妥当でなければ発行できない", () => {
    render(<DialogHarness />)
    expect(screen.getByText("1", { exact: true })).toBeInTheDocument()
    expect(screen.getByText("2", { exact: true })).toBeInTheDocument()
    expect(screen.getByText("発行するチケットの設定を行ってください。")).toBeInTheDocument()
    expect(screen.getByText("期限")).toBeInTheDocument()
    expect(screen.getByText("〜")).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText("開始日"), { target: { value: "" } })
    expect(screen.getByRole("alert")).toHaveTextContent("開始日と終了日は必須")
    expect(screen.getByRole("button", { name: "Backlogに2件発行" })).toBeDisabled()
    fireEvent.change(screen.getByLabelText("開始日"), { target: { value: "2025-07-01" } })
    expect(screen.getByRole("alert")).toHaveTextContent("開始日は終了日以前")
  })

  it("想定担当者数を1人以上で増減できる", () => {
    render(<DialogHarness />)
    fireEvent.click(screen.getByRole("button", { name: "想定担当者数を減らす" }))
    fireEvent.click(screen.getByRole("button", { name: "想定担当者数を減らす" }))
    expect(screen.getByLabelText("想定担当者数: 1人")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "想定担当者数を減らす" })).toBeDisabled()
    fireEvent.click(screen.getByRole("button", { name: "想定担当者数を増やす" }))
    expect(screen.getByLabelText("想定担当者数: 2人")).toBeInTheDocument()
  })

  it("個別選択、全選択、全解除と件数を同期する", () => {
    render(<DialogHarness />)
    fireEvent.click(screen.getByRole("checkbox", { name: "要件を確認する" }))
    expect(screen.getByText("1件を選択中")).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "全選択" }))
    expect(screen.getByText("3件を選択中")).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "全解除" }))
    expect(screen.getByText("0件を選択中")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Backlogに0件発行" })).toBeDisabled()
  })

  it("妥当な値だけをコールバックに渡し、閉じて再度開くと初期化する", () => {
    render(<DialogHarness />)
    fireEvent.click(screen.getByRole("button", { name: "想定担当者数を増やす" }))
    fireEvent.click(screen.getByRole("button", { name: "全選択" }))
    fireEvent.click(screen.getByRole("button", { name: "Backlogに3件発行" }))
    expect(onSubmit).toHaveBeenCalledWith({ startDate: "2025-06-01", endDate: "2025-06-30", expectedAssigneeCount: 4, taskIds: ["task-1", "task-2", "task-3"] })
    fireEvent.click(screen.getByRole("button", { name: "キャンセル" }))
    expect(onClose).toHaveBeenCalledTimes(1)
    fireEvent.click(screen.getByRole("button", { name: "開く" }))
    expect(screen.getByText("2件を選択中")).toBeInTheDocument()
    expect(screen.getByLabelText("想定担当者数: 3人")).toBeInTheDocument()
  })

  it("Escapeで閉じられ、入力名と選択状態を判別できる", () => {
    render(<DialogHarness />)
    expect(screen.getByRole("checkbox", { name: "要件を確認する" })).toBeChecked()
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" })
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it("閉じるボタンで閉じられる", () => {
    render(<DialogHarness />)
    fireEvent.click(screen.getByRole("button", { name: "Close" }))
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})
