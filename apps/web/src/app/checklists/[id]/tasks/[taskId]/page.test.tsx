import { cleanup, render, screen, within } from "@testing-library/react"
import { afterEach, expect, test, vi } from "vitest"

const notFoundMock = vi.hoisted(() => vi.fn(() => { throw new Error("NEXT_NOT_FOUND") }))
const taskFormMock = vi.hoisted(() => vi.fn(({ initialValues }) => <div data-testid="task-form">{JSON.stringify(initialValues)}</div>))

vi.mock("next/navigation", () => ({ notFound: notFoundMock }))
vi.mock("@/components/app-sidebar", () => ({ AppSidebar: () => <aside /> }))
vi.mock("@/components/app-breadcrumb", () => ({
  AppBreadcrumb: ({ items }: { items: { label: string; href?: string }[] }) => (
    <nav aria-label="パンくず">
      {items.map((item) => item.href ? <a key={item.label} href={item.href}>{item.label}</a> : <span key={item.label} aria-current="page">{item.label}</span>)}
    </nav>
  ),
}))
vi.mock("./task-form", () => ({ TaskForm: taskFormMock }))

import TaskDetailPage from "./page"

afterEach(() => {
  cleanup()
  notFoundMock.mockReset()
  taskFormMock.mockClear()
})

test("対象タスクのパンくずと初期値を表示する", async () => {
  render(await TaskDetailPage({ params: Promise.resolve({ id: "1", taskId: "travel-arrangements" }) }))

  expect(screen.getByRole("link", { name: "チェックリスト" })).toHaveAttribute("href", "/")
  expect(screen.getByRole("link", { name: "出張の準備" })).toHaveAttribute("href", "/checklists/1")
  expect(
    within(screen.getByRole("navigation", { name: "パンくず" })).getByText("交通機関と宿泊先を手配する")
  ).toHaveAttribute("aria-current", "page")
  expect(taskFormMock).toHaveBeenCalledWith(expect.objectContaining({
    checklistId: "1",
    taskId: "travel-arrangements",
    initialValues: {
      title: "交通機関と宿泊先を手配する",
      summary: "移動時間と宿泊先を確定し、予約内容を共有します。",
      estimatedHours: "1",
      priority: "high",
    },
  }), undefined)
})

test("優先順位が未設定のタスクは中を初期値にする", async () => {
  render(await TaskDetailPage({ params: Promise.resolve({ id: "1", taskId: "packing" }) }))

  expect(taskFormMock).toHaveBeenCalledWith(expect.objectContaining({
    initialValues: expect.objectContaining({ priority: "medium" }),
  }), undefined)
})

test.each([
  { id: "unknown", taskId: "travel-arrangements" },
  { id: "2", taskId: "travel-arrangements" },
  { id: "1", taskId: "unknown" },
])("未知または親子不一致では404を返す", async ({ id, taskId }) => {
  await expect(TaskDetailPage({ params: Promise.resolve({ id, taskId }) })).rejects.toThrow("NEXT_NOT_FOUND")
  expect(notFoundMock).toHaveBeenCalledOnce()
})
