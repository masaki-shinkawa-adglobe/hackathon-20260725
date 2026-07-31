import { cleanup, render, screen } from "@testing-library/react"
import type { ComponentProps } from "react"
import { afterEach, expect, test, vi } from "vitest"

const useActionStateMock = vi.hoisted(() => vi.fn())
const useFormStatusMock = vi.hoisted(() => vi.fn())

vi.mock("next/link", () => ({ default: ({ children, ...props }: ComponentProps<"a">) => <a {...props}>{children}</a> }))
vi.mock("react", async (importOriginal) => ({ ...(await importOriginal<typeof import("react")>()), useActionState: useActionStateMock }))
vi.mock("react-dom", () => ({ useFormStatus: useFormStatusMock }))

import { TaskForm } from "./task-form"

afterEach(() => {
  cleanup()
  useActionStateMock.mockReset()
  useFormStatusMock.mockReset()
})

test("エラー時に入力値、アクセシビリティ属性、キャンセルリンクを保持する", () => {
  useActionStateMock.mockReturnValue([{
    errors: { title: "タスク名を入力してください。", estimatedHours: "工数エラー", priority: "優先順位エラー" },
    values: { title: "入力済み", summary: "本文", estimatedHours: "0", priority: "high" },
  }, vi.fn()])
  useFormStatusMock.mockReturnValue({ pending: false })

  render(<TaskForm checklistId="1" taskId="packing" initialValues={{ title: "初期", summary: "初期本文", estimatedHours: "1", priority: "medium" }} />)

  expect(screen.getByLabelText("タスク名")).toHaveValue("入力済み")
  expect(screen.getByLabelText("本文")).toHaveValue("本文")
  expect(screen.getByLabelText("工数（時間）")).toHaveValue(0)
  expect(screen.getByLabelText("優先順位")).toHaveValue("high")
  expect(screen.getByLabelText("タスク名")).toHaveAttribute("aria-invalid", "true")
  expect(screen.getByLabelText("タスク名")).toHaveAttribute("aria-describedby", "title-error")
  expect(screen.getByRole("link", { name: "キャンセル" })).toHaveAttribute("href", "/checklists/1")
})

test("送信中は保存ボタンを無効化する", () => {
  useActionStateMock.mockReturnValue([{ errors: {}, values: { title: "タスク", summary: "本文", estimatedHours: "1", priority: "medium" } }, vi.fn()])
  useFormStatusMock.mockReturnValue({ pending: true })

  render(<TaskForm checklistId="1" taskId="packing" initialValues={{ title: "初期", summary: "初期本文", estimatedHours: "1", priority: "medium" }} />)

  expect(screen.getByRole("button", { name: "保存中..." })).toBeDisabled()
  expect(screen.getByLabelText("タスク名")).toBeDisabled()
  expect(screen.getByLabelText("本文")).toBeDisabled()
  expect(screen.getByLabelText("工数（時間）")).toBeDisabled()
  expect(screen.getByLabelText("優先順位")).toBeDisabled()
})
