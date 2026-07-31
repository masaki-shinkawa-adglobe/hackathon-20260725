import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { useState } from "react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { AIBulkTasksDialog } from "./ai-bulk-tasks-dialog"

const onOpenChange = vi.fn()
const onSuccess = vi.fn()

function renderDialog() {
  return render(<AIBulkTasksDialog checklistId={12} open onOpenChange={onOpenChange} onSuccess={onSuccess} />)
}

function DialogHarness() {
  const [open, setOpen] = useState(true)
  return <><button type="button" onClick={() => setOpen(true)}>開く</button><AIBulkTasksDialog checklistId={12} open={open} onOpenChange={setOpen} onSuccess={onSuccess} /></>
}

describe("AIBulkTasksDialog", () => {
  afterEach(() => {
    cleanup()
    onOpenChange.mockReset()
    onSuccess.mockReset()
    vi.unstubAllGlobals()
  })

  it("説明とファイルの少なくとも一方を要求し、文字数を表示する", () => {
    renderDialog()

    fireEvent.click(screen.getByRole("button", { name: "AIで登録" }))
    expect(screen.getByRole("alert")).toHaveTextContent("説明またはファイルを入力してください。")

    fireEvent.change(screen.getByLabelText("説明（任意）"), { target: { value: "確認作業を分解する" } })
    expect(screen.getByText("9 / 10,000")).toBeInTheDocument()
  })

  it("選択ファイルを表示、変更、削除でき、サイズを検証する", () => {
    renderDialog()
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    expect(screen.getByLabelText("資料ファイル（任意）")).toBe(input)
    expect(input).toHaveAttribute("tabindex", "-1")
    const csv = new File(["name"], "tasks.csv", { type: "text/csv" })
    fireEvent.change(input, { target: { files: [csv] } })
    expect(screen.getByText(/tasks\.csv/)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "変更" })).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "削除" }))
    expect(screen.queryByText(/tasks\.csv/)).not.toBeInTheDocument()

    const tooLarge = new File([new Uint8Array(10 * 1024 * 1024 + 1)], "large.txt", { type: "text/plain" })
    fireEvent.change(input, { target: { files: [tooLarge] } })
    expect(screen.getByRole("alert")).toHaveTextContent("10 MiB以下")
  })

  it("FormDataを送信し、成功時にタスクを返して閉じ、次回は初期化する", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ tasks: [{ id: 1, checklist_id: 12, title: "確認", summary: "確認する", estimated_hours: 1 }] }), { status: 200 }))
    vi.stubGlobal("fetch", fetchMock)
    render(<DialogHarness />)
    fireEvent.change(screen.getByLabelText("説明（任意）"), { target: { value: "説明" } })
    const fileInput = screen.getByLabelText("資料ファイル（任意）")
    fireEvent.change(fileInput, { target: { files: [new File(["data"], "tasks.csv", { type: "text/csv" })] } })
    fireEvent.click(screen.getByRole("button", { name: "AIで登録" }))

    await waitFor(() => expect(onSuccess).toHaveBeenCalledWith(expect.arrayContaining([expect.objectContaining({ title: "確認" })])))
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(init.body).toBeInstanceOf(FormData)
    expect((init.body as FormData).get("checklist_id")).toBe("12")
    expect((init.body as FormData).get("description")).toBe("説明")
    expect((init.body as FormData).get("file")).toMatchObject({ name: "tasks.csv" })
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "開く" }))
    expect(screen.getByLabelText("説明（任意）")).toHaveValue("")
    expect(screen.queryByText(/tasks\.csv/)).not.toBeInTheDocument()
  })

  it("APIエラー時は入力を保持し、送信中はキャンセルできない", async () => {
    let resolveFetch: (value: Response) => void = () => undefined
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>((resolve) => { resolveFetch = resolve })))
    renderDialog()
    fireEvent.change(screen.getByLabelText("説明（任意）"), { target: { value: "保持する説明" } })
    fireEvent.click(screen.getByRole("button", { name: "AIで登録" }))
    expect(screen.getByRole("button", { name: "キャンセル" })).toBeDisabled()
    resolveFetch(new Response(JSON.stringify({ detail: "no" }), { status: 422 }))
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("入力内容またはファイル"))
    expect(screen.getByLabelText("説明（任意）")).toHaveValue("保持する説明")
  })

  it.each([
    [404, undefined, "指定したチェックリストが見つかりません。"],
    [413, undefined, "ファイルサイズは10 MiB以下にしてください。"],
    [415, undefined, "PDF、XLSX、CSV、TXT形式のファイルを選択してください。"],
    [502, "upstream_error", "AI連携で問題が発生しました。時間をおいて再試行してください。"],
    [503, "upstream_error", "AI連携で問題が発生しました。時間をおいて再試行してください。"],
    [502, "proxy_connection_failed", "AIタスクの登録に失敗しました。時間をおいて再試行してください。"],
    [503, "proxy_not_configured", "AIタスクの登録に失敗しました。時間をおいて再試行してください。"],
  ])("HTTP %i の code=%s を適切に表示する", async (status, code, message) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ code }), { status })))
    renderDialog()
    fireEvent.change(screen.getByLabelText("説明（任意）"), { target: { value: "説明" } })
    fireEvent.click(screen.getByRole("button", { name: "AIで登録" }))
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(message))
  })

  it("送信中はEscape、背景クリック、閉じるボタンで閉じられない", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(() => {})))
    renderDialog()
    fireEvent.change(screen.getByLabelText("説明（任意）"), { target: { value: "説明" } })
    fireEvent.click(screen.getByRole("button", { name: "AIで登録" }))
    const dialog = screen.getByRole("dialog")
    fireEvent.keyDown(dialog, { key: "Escape" })
    fireEvent.pointerDown(document.querySelector('[data-slot="dialog-overlay"]') as Element)
    expect(screen.getByRole("dialog")).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Close" })).not.toBeInTheDocument()
    expect(onOpenChange).not.toHaveBeenCalledWith(false)
  })

  it("キャンセル後は入力を破棄する", () => {
    render(<DialogHarness />)
    fireEvent.change(screen.getByLabelText("説明（任意）"), { target: { value: "破棄する説明" } })
    fireEvent.click(screen.getByRole("button", { name: "キャンセル" }))
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "開く" }))
    expect(screen.getByLabelText("説明（任意）")).toHaveValue("")
  })
})
