import { cleanup, render, screen } from "@testing-library/react"
import type { ComponentProps } from "react"
import { afterEach, expect, test, vi } from "vitest"

const notFoundMock = vi.hoisted(() =>
  vi.fn(() => {
    throw new Error("NEXT_NOT_FOUND")
  })
)

vi.mock("next/link", () => ({
  default: ({ children, ...props }: ComponentProps<"a">) => <a {...props}>{children}</a>,
}))

vi.mock("next/navigation", () => ({
  notFound: notFoundMock,
}))

import ChecklistDetailPage from "./page"

afterEach(() => {
  cleanup()
  notFoundMock.mockReset()
})

test("チェックリスト名、説明、タスク一覧を表示する", async () => {
  render(await ChecklistDetailPage({ params: Promise.resolve({ id: "1" }) }))

  expect(screen.getByRole("heading", { level: 1, name: "出張の準備" })).toBeInTheDocument()
  expect(screen.getByText("出張前に必要な準備を確認するチェックリストです。"))
    .toBeInTheDocument()
  expect(screen.getByRole("columnheader", { name: "タイトル" })).toHaveAttribute("scope", "col")
  expect(screen.getByText("交通機関と宿泊先を手配する")).toBeInTheDocument()
  expect(screen.getByRole("link", { name: "交通機関と宿泊先を手配する" })).toHaveAttribute(
    "href",
    "/checklists/1/tasks/travel-arrangements"
  )
  expect(screen.getByText("1時間")).toBeInTheDocument()
})

test("タスクがないチェックリストでは空状態を表示する", async () => {
  render(await ChecklistDetailPage({ params: Promise.resolve({ id: "2" }) }))

  expect(screen.getByText("タスクはまだ登録されていません")).toBeInTheDocument()
  expect(screen.queryByRole("table")).not.toBeInTheDocument()
})

test("一覧と編集へのリンクを表示する", async () => {
  render(await ChecklistDetailPage({ params: Promise.resolve({ id: "1" }) }))

  expect(screen.getByRole("link", { name: "チェックリスト一覧へ戻る" })).toHaveAttribute("href", "/")
  expect(screen.getByRole("link", { name: "編集する" })).toHaveAttribute(
    "href",
    "/checklists/1/edit"
  )
})

test("未知のIDでは404を返す", async () => {
  await expect(
    ChecklistDetailPage({ params: Promise.resolve({ id: "unknown" }) })
  ).rejects.toThrow("NEXT_NOT_FOUND")

  expect(notFoundMock).toHaveBeenCalledOnce()
})
