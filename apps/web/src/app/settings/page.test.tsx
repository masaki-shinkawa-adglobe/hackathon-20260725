import { cleanup, render, screen, within } from "@testing-library/react"
import type { ComponentProps } from "react"
import { afterEach, expect, test, vi } from "vitest"

vi.mock("next/link", () => ({
  default: ({ children, ...props }: ComponentProps<"a">) => (
    <a {...props}>{children}</a>
  ),
}))

vi.mock("next/navigation", () => ({
  usePathname: () => "/settings",
}))

import SettingsPage from "./page"

afterEach(cleanup)

test("管理・連携設定の主要表示とパンくずを表示する", () => {
  render(<SettingsPage />)

  expect(screen.getByRole("heading", { name: "管理・連携設定", level: 1 })).toBeInTheDocument()
  const settingsLinks = screen.getAllByRole("link", { name: "管理・連携設定" })
  expect(settingsLinks[0]).toHaveAttribute("aria-current", "page")
  expect(settingsLinks[1]).toHaveAttribute("href", "/settings")
  expect(screen.getByRole("link", { name: "連携設定" })).toHaveAttribute("aria-current", "page")
})

test("3つの連携カードに必須フィールドとComing Soon状態を表示する", () => {
  render(<SettingsPage />)

  expect(screen.getAllByText("Coming Soon")).toHaveLength(3)
  expect(screen.getByLabelText("ドメイン")).toBeDisabled()
  expect(screen.getByLabelText("APIキー")).toBeDisabled()
  expect(screen.getByLabelText("Webhook URL")).toBeDisabled()
  expect(screen.getByLabelText("アカウント")).toBeDisabled()
  expect(screen.getByLabelText("カレンダー")).toBeDisabled()

  for (const service of ["Backlog", "Slack", "Googleカレンダー"]) {
    const card = screen.getByRole("heading", { name: service }).closest("section")
    expect(card).not.toBeNull()
    expect(within(card!).getByRole("group")).toBeDisabled()
    expect(within(card!).getByRole("button", { name: "接続テスト" })).toBeDisabled()
    expect(within(card!).getByRole("button", { name: "保存" })).toBeDisabled()
  }
})

test("接続履歴のモックデータを表示する", () => {
  render(<SettingsPage />)

  expect(screen.getByRole("heading", { name: "接続履歴" })).toBeInTheDocument()
  expect(screen.getByRole("columnheader", { name: "サービス" })).toBeInTheDocument()
  expect(screen.getByRole("columnheader", { name: "最終接続確認" })).toBeInTheDocument()
  expect(screen.getByRole("columnheader", { name: "ステータス" })).toBeInTheDocument()
  expect(screen.getAllByRole("cell", { name: "未接続" })).toHaveLength(6)
})
