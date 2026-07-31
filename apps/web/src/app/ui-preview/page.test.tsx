import { act, cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

const navigationMock = vi.hoisted(() => ({ pathname: "/ui-preview" }))

vi.mock("next/link", () => ({
  default: ({ children, ...props }: React.ComponentProps<"a">) => <a {...props}>{children}</a>,
}))

vi.mock("next/navigation", () => ({
  usePathname: () => navigationMock.pathname,
}))

import UiPreviewPage from "./page"

describe("UiPreviewPage", () => {
  afterEach(() => {
    cleanup()
    vi.useRealTimers()
  })

  it("共通ナビゲーション、ボタン、初期のmock行を表示する", () => {
    render(<UiPreviewPage />)

    expect(screen.getByText("UIプレビュー")).toBeInTheDocument()
    expect(screen.queryByRole("link", { name: /ホーム/i })).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: "default" })).toHaveAttribute("data-variant", "default")
    expect(screen.getByRole("button", { name: "outline" })).toHaveAttribute("data-variant", "outline")
    expect(screen.getByRole("button", { name: "destructive" })).toHaveAttribute("data-variant", "destructive")
    expect(screen.getByRole("button", { name: "ghost" })).toHaveAttribute("data-variant", "ghost")
    expect(screen.getByText("出張準備")).toBeInTheDocument()
  })

  it("固定サイドバー幅を通常フローで確保してからメイン領域を配置する", () => {
    render(<UiPreviewPage />)

    const main = screen.getByRole("main")
    const sidebarOffset = screen.getByTestId("sidebar-offset")
    expect(main).toHaveClass("flex-1")
    expect(main).not.toHaveClass("md:ml-[var(--sidebar-width)]")
    expect(main.parentElement).toHaveClass("flex")
    expect(main.parentElement).toHaveClass("[&>[data-slot=sidebar-wrapper]]:contents")
    expect(main.parentElement?.querySelector('[data-slot="sidebar-wrapper"]')).toBeInTheDocument()
    expect(sidebarOffset).toHaveClass("hidden", "shrink-0", "md:block", "md:w-64")
    expect(main.previousElementSibling).toBe(sidebarOffset)
  })

  it("検索とソート条件に応じて親側でmock行を差し替える", () => {
    vi.useFakeTimers()
    render(<UiPreviewPage />)

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
    render(<UiPreviewPage />)

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
    render(<UiPreviewPage />)

    fireEvent.click(screen.getByRole("button", { name: `サイズ: ${size}` }))
    expect(screen.getByRole("dialog")).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "完了" }))
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
  })
})
