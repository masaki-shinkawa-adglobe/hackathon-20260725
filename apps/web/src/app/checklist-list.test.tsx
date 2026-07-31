import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react"
import { afterEach, expect, test, vi } from "vitest"

import { ChecklistList } from "./checklist-list"

const checklists = [
  { id: 1, name: "出張の準備", task_count: 6, updated_at: "2026-07-30T14:30:00" },
  { id: 2, name: "新入社員の受け入れ", task_count: 8, updated_at: "2026-07-29T10:15:00" },
]

afterEach(() => {
  cleanup()
  vi.useRealTimers()
})

test("APIの一覧項目を表示し、名前から詳細へ遷移できる", () => {
  render(<ChecklistList checklists={checklists} />)

  expect(screen.getAllByRole("columnheader").map((header) => header.textContent)).toEqual([
    "チェックリスト名", "登録タスク数", "最終更新日時",
  ])
  const row = screen.getByRole("row", { name: /出張の準備/ })
  expect(within(row).getByRole("link", { name: "出張の準備" })).toHaveAttribute("href", "/checklists/1")
  expect(within(row).getByRole("cell", { name: "6" })).toBeInTheDocument()
  expect(within(row).getByRole("cell", { name: "2026-07-30T14:30:00" })).toBeInTheDocument()
})

test("名前だけで部分一致検索する", () => {
  vi.useFakeTimers()
  render(<ChecklistList checklists={checklists} />)

  fireEvent.change(screen.getByRole("searchbox", { name: "検索" }), { target: { value: "新入社員" } })
  act(() => vi.advanceTimersByTime(300))

  expect(screen.getByRole("link", { name: "新入社員の受け入れ" })).toBeInTheDocument()
  expect(screen.queryByRole("link", { name: "出張の準備" })).not.toBeInTheDocument()
  expect(screen.getByText("全 1 件")).toBeInTheDocument()
})
