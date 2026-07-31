import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, expect, test, vi } from "vitest"

vi.mock("./checklist-detail", () => ({
  ChecklistDetail: ({ checklistId }: { checklistId: string }) => (
    <div data-testid="checklist-detail">{checklistId}</div>
  ),
}))

import ChecklistDetailPage from "./page"

afterEach(() => {
  cleanup()
})

test("URLのIDを詳細コンポーネントへ渡す", async () => {
  render(await ChecklistDetailPage({ params: Promise.resolve({ id: "42" }) }))

  expect(screen.getByTestId("checklist-detail")).toHaveTextContent("42")
})
