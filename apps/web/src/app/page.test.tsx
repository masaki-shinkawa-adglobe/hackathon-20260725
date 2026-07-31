import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react"
import { afterEach, expect, test, vi } from "vitest"

const pushMock = vi.hoisted(() => vi.fn())

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
  useRouter: () => ({ push: pushMock }),
}))

import Home from "./page"

afterEach(() => {
  cleanup()
  vi.useRealTimers()
  pushMock.mockReset()
})

test("チェックリスト一覧の全列見出しとモックデータを表示する", () => {
  render(<Home />)

  expect(screen.getByRole("heading", { name: "チェックリスト一覧", level: 1 })).toBeInTheDocument()
  expect(screen.getByText("キーワード")).toBeInTheDocument()
  expect(screen.getByRole("link", { name: "新規作成" })).toHaveAttribute("href", "/checklists/new")
  expect(screen.getByText("全 3 件")).toBeInTheDocument()
  expect(screen.getAllByRole("columnheader").map((header) => header.textContent)).toEqual([
    "チェックリスト名",
    "登録タスク数",
    "Backlog最終登録日時",
    "最終更新日時",
  ])

  const businessTripRow = screen.getByRole("row", { name: /出張の準備/ })
  expect(within(businessTripRow).getByRole("link", { name: "出張の準備" })).toHaveAttribute(
    "href",
    "/checklists/business-trip"
  )
  expect(within(businessTripRow).getByRole("cell", { name: "出張の準備" })).toBeInTheDocument()
  expect(within(businessTripRow).getByRole("cell", { name: "6" })).toBeInTheDocument()
  expect(within(businessTripRow).getByRole("cell", { name: "2026年7月30日 13:45" })).toBeInTheDocument()
  expect(within(businessTripRow).getByRole("cell", { name: "2026年7月30日 14:30" })).toBeInTheDocument()

  const newEmployeeRow = screen.getByRole("row", { name: /新入社員の受け入れ/ })
  expect(within(newEmployeeRow).getByRole("cell", { name: "新入社員の受け入れ" })).toBeInTheDocument()
  expect(within(newEmployeeRow).getByRole("cell", { name: "8" })).toBeInTheDocument()
  expect(within(newEmployeeRow).getByRole("cell", { name: "2026年7月29日 09:50" })).toBeInTheDocument()
  expect(within(newEmployeeRow).getByRole("cell", { name: "2026年7月29日 10:15" })).toBeInTheDocument()

  const monthlyClosingRow = screen.getByRole("row", { name: /月次締め作業/ })
  expect(within(monthlyClosingRow).getByRole("cell", { name: "月次締め作業" })).toBeInTheDocument()
  expect(within(monthlyClosingRow).getByRole("cell", { name: "5" })).toBeInTheDocument()
  expect(within(monthlyClosingRow).getByRole("cell", { name: "2026年7月28日 16:30" })).toBeInTheDocument()
  expect(within(monthlyClosingRow).getByRole("cell", { name: "2026年7月28日 17:45" })).toBeInTheDocument()
})

test("チェックリストの行をクリックすると詳細画面へ遷移する", () => {
  render(<Home />)

  fireEvent.click(screen.getByRole("cell", { name: "6" }))

  expect(pushMock).toHaveBeenCalledWith("/checklists/business-trip")
})

test("名前の部分一致で該当するチェックリストだけを表示する", () => {
  vi.useFakeTimers()
  render(<Home />)

  fireEvent.change(screen.getByRole("searchbox", { name: "検索" }), {
    target: { value: "新入社員" },
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
