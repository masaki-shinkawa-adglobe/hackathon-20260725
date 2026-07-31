import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react"
import { afterEach, expect, test, vi } from "vitest"

import Home from "./page"

afterEach(() => {
  cleanup()
  vi.useRealTimers()
})

test("チェックリスト一覧の全列見出しとモックデータを表示する", () => {
  render(<Home />)

  expect(screen.getByRole("heading", { name: "チェックリスト一覧", level: 1 })).toBeInTheDocument()
  expect(screen.getByText("キーワード")).toBeInTheDocument()
  expect(screen.getByRole("link", { name: "新規作成" })).toHaveAttribute("href", "/checklists/new")
  expect(screen.getByText("全 3 件")).toBeInTheDocument()
  expect(screen.getByRole("columnheader", { name: "チェックリスト名" })).toHaveAttribute("scope", "col")
  expect(screen.getByRole("columnheader", { name: "説明" })).toHaveAttribute("scope", "col")
  expect(screen.getByRole("columnheader", { name: "完了済み項目数" })).toHaveAttribute("scope", "col")
  expect(screen.getByRole("columnheader", { name: "総項目数" })).toHaveAttribute("scope", "col")
  expect(screen.getByRole("columnheader", { name: "更新日時" })).toHaveAttribute("scope", "col")

  const businessTripRow = screen.getByRole("row", { name: /出張の準備/ })
  expect(within(businessTripRow).getByRole("cell", { name: "出張の準備" })).toBeInTheDocument()
  expect(within(businessTripRow).getByRole("cell", { name: "来週の大阪出張に必要な持ち物と手配を確認します。" })).toBeInTheDocument()
  expect(within(businessTripRow).getByRole("cell", { name: "4" })).toBeInTheDocument()
  expect(within(businessTripRow).getByRole("cell", { name: "6" })).toBeInTheDocument()
  expect(within(businessTripRow).getByRole("cell", { name: "2026年7月30日 14:30" })).toBeInTheDocument()

  const newEmployeeRow = screen.getByRole("row", { name: /新入社員の受け入れ/ })
  expect(within(newEmployeeRow).getByRole("cell", { name: "新入社員の受け入れ" })).toBeInTheDocument()
  expect(within(newEmployeeRow).getByRole("cell", { name: "入社初日に必要なアカウント発行と備品準備の一覧です。" })).toBeInTheDocument()
  expect(within(newEmployeeRow).getByRole("cell", { name: "7" })).toBeInTheDocument()
  expect(within(newEmployeeRow).getByRole("cell", { name: "8" })).toBeInTheDocument()
  expect(within(newEmployeeRow).getByRole("cell", { name: "2026年7月29日 10:15" })).toBeInTheDocument()

  const monthlyClosingRow = screen.getByRole("row", { name: /月次締め作業/ })
  expect(within(monthlyClosingRow).getByRole("cell", { name: "月次締め作業" })).toBeInTheDocument()
  expect(within(monthlyClosingRow).getByRole("cell", { name: "経費精算とレポート提出の進捗を管理します。" })).toBeInTheDocument()
  expect(within(monthlyClosingRow).getByRole("cell", { name: "2" })).toBeInTheDocument()
  expect(within(monthlyClosingRow).getByRole("cell", { name: "5" })).toBeInTheDocument()
  expect(within(monthlyClosingRow).getByRole("cell", { name: "2026年7月28日 17:45" })).toBeInTheDocument()
})

test("名前または説明の部分一致で該当するチェックリストだけを表示する", () => {
  vi.useFakeTimers()
  render(<Home />)

  fireEvent.change(screen.getByRole("searchbox", { name: "検索" }), {
    target: { value: "アカウント発行" },
  })
  act(() => {
    vi.advanceTimersByTime(300)
  })

  expect(screen.getByRole("cell", { name: "新入社員の受け入れ" })).toBeInTheDocument()
  expect(screen.queryByRole("cell", { name: "出張の準備" })).not.toBeInTheDocument()
  expect(screen.queryByRole("cell", { name: "月次締め作業" })).not.toBeInTheDocument()
  expect(screen.getByText("全 1 件")).toBeInTheDocument()
})

test("一致しない検索語では空状態を表示する", () => {
  vi.useFakeTimers()
  render(<Home />)

  fireEvent.change(screen.getByRole("searchbox", { name: "検索" }), {
    target: { value: "存在しないチェックリスト" },
  })
  act(() => {
    vi.advanceTimersByTime(300)
  })

  expect(screen.getByText("該当するチェックリストがありません。")).toBeInTheDocument()
  expect(screen.getByText("全 0 件")).toBeInTheDocument()
})
