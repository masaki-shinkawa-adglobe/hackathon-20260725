import { act, cleanup, fireEvent, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { toast } from "sonner"
import { Toaster } from "@/components/ui/sonner"

const navigationMock = vi.hoisted(() => ({ pathname: "/ui-preview" }))

vi.mock("next/link", () => ({
  default: ({ children, ...props }: React.ComponentProps<"a">) => <a {...props}>{children}</a>,
}))

vi.mock("next/navigation", () => ({
  usePathname: () => navigationMock.pathname,
}))

import UiPreviewPage from "./page"

function renderPreview() {
  return render(
    <>
      <UiPreviewPage />
      <Toaster />
    </>
  )
}

describe("UiPreviewPage", () => {
  afterEach(() => {
    cleanup()
    act(() => toast.dismiss())
    vi.useRealTimers()
  })

  it("共通ナビゲーション、ボタン、初期のmock行を表示する", () => {
    renderPreview()

    expect(screen.getByText("UIプレビュー")).toBeInTheDocument()
    expect(screen.queryByRole("link", { name: /ホーム/i })).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: "default" })).toHaveAttribute("data-variant", "default")
    expect(screen.getByRole("button", { name: "outline" })).toHaveAttribute("data-variant", "outline")
    expect(screen.getByRole("button", { name: "destructive" })).toHaveAttribute("data-variant", "destructive")
    expect(screen.getByRole("button", { name: "ghost" })).toHaveAttribute("data-variant", "ghost")
    expect(screen.getByText("出張準備")).toBeInTheDocument()
  })

  it("AppSidebarに必要なSidebarProvider内で固定サイドバー幅を確保してからメイン領域を配置する", () => {
    renderPreview()

    const main = screen.getByRole("main")
    const sidebarOffset = screen.getByTestId("sidebar-offset")
    expect(main).toHaveClass("flex-1")
    expect(main).not.toHaveClass("md:ml-[var(--sidebar-width)]")
    expect(main.parentElement).toHaveClass("flex")
    expect(main.parentElement).toHaveClass("[&>[data-slot=sidebar-wrapper]]:contents")
    expect(main.parentElement).toHaveAttribute("data-slot", "sidebar-wrapper")
    expect(main.parentElement?.querySelector('[data-slot="sidebar"]')).toBeInTheDocument()
    expect(sidebarOffset).toHaveClass("hidden", "shrink-0", "md:block", "md:w-64")
    expect(main.previousElementSibling).toBe(sidebarOffset)
  })

  it("検索とソート条件に応じて親側でmock行を差し替える", () => {
    vi.useFakeTimers()
    renderPreview()

    fireEvent.change(screen.getByRole("searchbox", { name: "検索" }), { target: { value: "イベント" } })
    act(() => vi.advanceTimersByTime(300))
    expect(screen.getByText("イベント準備")).toBeInTheDocument()
    expect(screen.queryByText("出張準備")).not.toBeInTheDocument()

    fireEvent.change(screen.getByRole("searchbox", { name: "検索" }), { target: { value: "" } })
    act(() => vi.advanceTimersByTime(300))
    fireEvent.click(screen.getByRole("button", { name: "「updatedAt」で並び替え" }))
    expect(screen.getAllByRole("row")[1]).toHaveTextContent("入社準備")
  })

  it("loading、error、空状態を切り替え、再試行で通常表示へ戻す", () => {
    renderPreview()

    fireEvent.click(screen.getByRole("button", { name: "loading" }))
    expect(screen.getAllByLabelText("読み込み中")).toHaveLength(3)

    fireEvent.click(screen.getByRole("button", { name: "error" }))
    expect(screen.getByText("データの取得に失敗しました。")).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "再試行" }))
    expect(screen.getByText("出張準備")).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "空データ" }))
    expect(screen.getByText("表示するチェックリストがありません。")).toBeInTheDocument()
  })

  it.each(["sm", "md", "lg"] as const)("%sのAppDialogを開閉できる", (size) => {
    renderPreview()

    fireEvent.click(screen.getByRole("button", { name: `サイズ: ${size}` }))
    expect(screen.getByRole("dialog")).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "完了" }))
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
  })

  it.each([
    ["default", "既定の通知"],
    ["success", "成功通知"],
    ["info", "情報通知"],
    ["warning", "警告通知"],
    ["error", "エラー通知"],
    ["loading", "処理中通知"],
  ])("%s Toastを表示できる", async (type, title) => {
    renderPreview()

    fireEvent.click(screen.getByRole("button", { name: `${type} Toast` }))

    expect(await screen.findByText(title)).toBeInTheDocument()
  })

  it("Toastのアクションをクリックで実行できる", async () => {
    renderPreview()

    fireEvent.click(screen.getByRole("button", { name: "アクション付きToast" }))
    fireEvent.click(await screen.findByRole("button", { name: "元に戻す" }))
    expect(screen.getByText("変更を元に戻しました。")).toBeInTheDocument()
  })

  it("ToastのアクションをEnterキーで実行できる", async () => {
    const user = userEvent.setup()
    renderPreview()

    fireEvent.click(screen.getByRole("button", { name: "アクション付きToast" }))
    const action = await screen.findByRole("button", { name: "元に戻す" })
    action.focus()
    expect(action).toHaveFocus()
    expect(screen.getByText("アクション結果はありません。")).toBeInTheDocument()

    await user.keyboard("{Enter}")

    expect(screen.getByText("変更を元に戻しました。")).toBeInTheDocument()
  })

  it.each([
    ["Promise成功Toast", "処理が完了しました"],
    ["Promise失敗Toast", "処理に失敗しました"],
  ])("%sでloadingから状態更新できる", async (buttonName, result) => {
    renderPreview()

    fireEvent.click(screen.getByRole("button", { name: buttonName }))
    expect(await screen.findByText("処理を実行しています")).toBeInTheDocument()
    expect(await screen.findByText(result)).toBeInTheDocument()
  })

  it("モーダル外のチェックリストIDでAI一括登録モーダルを開ける", () => {
    render(<UiPreviewPage />)

    fireEvent.change(screen.getByLabelText("チェックリストID"), { target: { value: "42" } })
    fireEvent.click(screen.getByRole("button", { name: "AIでタスクを一括登録" }))
    expect(screen.getByRole("dialog")).toHaveTextContent("AIでタスクを一括登録")
    expect(screen.getByRole("dialog")).not.toHaveTextContent("チェックリストID")
  })

  it("AI一括登録の成功タスク一覧を表示する", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ tasks: [{ id: 1, checklist_id: 1, title: "AI作成タスク", summary: "概要", estimated_hours: 1 }] }), { status: 200 }))
    vi.stubGlobal("fetch", fetchMock)
    render(<UiPreviewPage />)

    fireEvent.click(screen.getByRole("button", { name: "AIでタスクを一括登録" }))
    fireEvent.change(screen.getByLabelText("説明（任意）"), { target: { value: "説明" } })
    fireEvent.click(screen.getByRole("button", { name: "AIで登録" }))

    expect(await screen.findByText("AI作成タスク")).toBeInTheDocument()
  })
})
