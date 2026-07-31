import { cleanup, render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"

const { pushMock, toastSuccessMock, toastErrorMock } = vi.hoisted(() => ({
  pushMock: vi.fn(),
  toastSuccessMock: vi.fn(),
  toastErrorMock: vi.fn(),
}))

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}))

vi.mock("sonner", () => ({
  toast: {
    success: toastSuccessMock,
    error: toastErrorMock,
  },
}))

import { ChecklistDeleteDialog } from "./checklist-delete-dialog"

describe("ChecklistDeleteDialog", () => {
  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
    pushMock.mockReset()
    toastSuccessMock.mockReset()
    toastErrorMock.mockReset()
  })

  it("確認ダイアログでローカルタスクとBacklog課題への影響を表示する", async () => {
    const user = userEvent.setup()
    render(<ChecklistDeleteDialog checklistId={1} />)

    await user.click(screen.getByRole("button", { name: "削除する" }))

    expect(screen.getByRole("dialog")).toBeInTheDocument()
    expect(screen.getByText("このチェックリストに含まれるローカルタスクも削除されます。Backlog上の課題は削除されません。")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "キャンセル" }))
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
  })

  it("確定時のみDELETEし、成功時に通知して一覧へ遷移する", async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }))
    vi.stubGlobal("fetch", fetchMock)
    render(<ChecklistDeleteDialog checklistId={1} />)

    await user.click(screen.getByRole("button", { name: "削除する" }))
    expect(fetchMock).not.toHaveBeenCalled()
    await user.click(within(screen.getByRole("dialog")).getByRole("button", { name: "削除する" }))

    expect(fetchMock).toHaveBeenCalledWith("/api/checklists/1", { method: "DELETE" })
    expect(toastSuccessMock).toHaveBeenCalledWith("チェックリストを削除しました。")
    expect(pushMock).toHaveBeenCalledWith("/")
  })

  it("失敗時はダイアログを維持して再実行できる", async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(null, { status: 500 }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
    vi.stubGlobal("fetch", fetchMock)
    render(<ChecklistDeleteDialog checklistId={1} />)

    await user.click(screen.getByRole("button", { name: "削除する" }))
    await user.click(within(screen.getByRole("dialog")).getByRole("button", { name: "削除する" }))

    expect(toastErrorMock).toHaveBeenCalledWith("チェックリストの削除に失敗しました。時間をおいて再試行してください。")
    expect(screen.getByRole("dialog")).toBeInTheDocument()
    expect(pushMock).not.toHaveBeenCalled()

    await user.click(within(screen.getByRole("dialog")).getByRole("button", { name: "削除する" }))
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(pushMock).toHaveBeenCalledWith("/")
  })

  it("削除中は二重送信とキャンセルを無効化する", async () => {
    const user = userEvent.setup()
    let resolveResponse: (response: Response) => void = () => undefined
    const fetchMock = vi.fn().mockReturnValue(new Promise<Response>((resolve) => { resolveResponse = resolve }))
    vi.stubGlobal("fetch", fetchMock)
    render(<ChecklistDeleteDialog checklistId={1} />)

    await user.click(screen.getByRole("button", { name: "削除する" }))
    const dialog = screen.getByRole("dialog")
    const confirmButton = within(dialog).getByRole("button", { name: "削除する" })
    await user.click(confirmButton)

    expect(screen.getByRole("button", { name: "削除中…" })).toBeDisabled()
    expect(screen.getByRole("button", { name: "キャンセル" })).toBeDisabled()
    await user.click(screen.getByRole("button", { name: "削除中…" }))
    expect(fetchMock).toHaveBeenCalledTimes(1)
    await user.keyboard("{Escape}")
    await user.click(document.querySelector('[data-slot="dialog-overlay"]')!)
    expect(screen.getByRole("dialog")).toBeInTheDocument()

    resolveResponse(new Response(null, { status: 204 }))
  })
})
