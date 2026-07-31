import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, expect, test, vi } from "vitest"

const checklistListMock = vi.hoisted(() => vi.fn(() => <div data-testid="checklist-list" />))

vi.mock("./checklist-list", () => ({
  ChecklistList: checklistListMock,
}))

import Home from "./page"

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  vi.unstubAllEnvs()
})

test("APIから取得したチェックリストを一覧コンポーネントへ渡す", async () => {
  vi.stubEnv("INTERNAL_API_URL", "http://api:8000")
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
    checklists: [{ id: 1, name: "出張の準備", task_count: 2, updated_at: "2026-07-30T14:30:00" }],
  }))))

  render(await Home())

  expect(screen.getByTestId("checklist-list")).toBeInTheDocument()
  expect(fetch).toHaveBeenCalledWith(new URL("http://api:8000/checklists"))
  expect(checklistListMock).toHaveBeenCalledWith({
    checklists: [{ id: 1, name: "出張の準備", task_count: 2, updated_at: "2026-07-30T14:30:00" }],
  }, undefined)
})
