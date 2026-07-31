import { expect, test, vi } from "vitest"

const redirectMock = vi.hoisted(() => vi.fn())

vi.mock("next/navigation", () => ({ redirect: redirectMock }))

import { updateTask } from "./actions"

function formData(values: Record<string, string>) {
  const data = new FormData()
  Object.entries(values).forEach(([key, value]) => data.set(key, value))
  return data
}

const previousState = {
  errors: {},
  values: { title: "", summary: "", estimatedHours: "", priority: "medium" },
}

test("不正な値では全入力値と各フィールドエラーを返す", async () => {
  const state = await updateTask(
    "1",
    "travel-arrangements",
    previousState,
    formData({ title: "  ", summary: "本文", estimatedHours: "0", priority: "urgent" })
  )

  expect(state.values).toEqual({ title: "  ", summary: "本文", estimatedHours: "0", priority: "urgent" })
  expect(state.errors).toEqual({
    title: "タスク名を入力してください。",
    estimatedHours: "工数には0より大きい数値を入力してください。",
    priority: "優先順位を選択してください。",
  })
  expect(redirectMock).not.toHaveBeenCalled()
})

test.each(["", "NaN", "Infinity", "-1"])("不正な工数 %s を拒否する", async (estimatedHours) => {
  const state = await updateTask(
    "1",
    "travel-arrangements",
    previousState,
    formData({ title: "タスク", summary: "本文", estimatedHours, priority: "medium" })
  )

  expect(state.errors.estimatedHours).toBeDefined()
})

test("有効な値では親チェックリスト詳細へ戻す", async () => {
  await updateTask(
    "1",
    "travel-arrangements",
    previousState,
    formData({ title: "タスク", summary: "本文", estimatedHours: "0.5", priority: "medium" })
  )

  expect(redirectMock).toHaveBeenCalledWith("/checklists/1")
})
