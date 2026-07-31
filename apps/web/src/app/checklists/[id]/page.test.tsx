import { cleanup, render, screen } from "@testing-library/react"
import type { ComponentProps } from "react"
import { afterEach, expect, test, vi } from "vitest"

const navigationMock = vi.hoisted(() => ({ notFound: vi.fn() }))

vi.mock("next/link", () => ({
  default: ({ children, ...props }: ComponentProps<"a">) => <a {...props}>{children}</a>,
}))

vi.mock("next/navigation", () => ({
  notFound: navigationMock.notFound,
}))

import ChecklistDetailPage from "./page"

afterEach(() => {
  cleanup()
  navigationMock.notFound.mockReset()
})

async function renderPage(id: string) {
  render(await ChecklistDetailPage({ params: Promise.resolve({ id }) }))
}

test("基本情報とタスク一覧を表示する", async () => {
  await renderPage("travel-preparation")

  expect(screen.getByRole("heading", { name: "出張準備チェックリスト", level: 1 })).toBeInTheDocument()
  expect(screen.getByText("出張前に必要な準備を確認するためのチェックリストです。")).toBeInTheDocument()
  expect(screen.getByRole("heading", { name: "タスク一覧", level: 2 })).toBeInTheDocument()
  expect(screen.getByRole("columnheader", { name: "タイトル" })).toBeInTheDocument()
  expect(screen.getByRole("columnheader", { name: "概要" })).toBeInTheDocument()
  expect(screen.getByRole("columnheader", { name: "工数" })).toBeInTheDocument()
  expect(screen.getByRole("cell", { name: "移動手段を予約する" })).toBeInTheDocument()
  expect(screen.getByRole("cell", { name: "1時間" })).toBeInTheDocument()
})

test("タスクが0件の場合は空状態を表示する", async () => {
  await renderPage("new-member-onboarding")

  expect(screen.getByText("タスクはまだ登録されていません")).toBeInTheDocument()
  expect(screen.queryByRole("table")).not.toBeInTheDocument()
})

test("一覧へ戻るリンクと編集リンクを表示する", async () => {
  await renderPage("travel-preparation")

  expect(screen.getByRole("link", { name: "一覧へ戻る" })).toHaveAttribute("href", "/")
  expect(screen.getByRole("link", { name: "編集" })).toHaveAttribute(
    "href",
    "/checklists/travel-preparation/edit",
  )
})

test("存在しないIDではnotFoundを呼び出す", async () => {
  navigationMock.notFound.mockImplementation(() => {
    throw new Error("NEXT_NOT_FOUND")
  })

  await expect(renderPage("unknown")).rejects.toThrow("NEXT_NOT_FOUND")
  expect(navigationMock.notFound).toHaveBeenCalledOnce()
})
