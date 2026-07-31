"use server"

import { redirect } from "next/navigation"

const priorities = ["low", "medium", "high"] as const

export type TaskFormState = {
  errors: {
    title?: string
    estimatedHours?: string
    priority?: string
  }
  values: {
    title: string
    summary: string
    estimatedHours: string
    priority: string
  }
}

export async function updateTask(
  checklistId: string,
  _taskId: string,
  _previousState: TaskFormState,
  formData: FormData
): Promise<TaskFormState> {
  const values = {
    title: String(formData.get("title") ?? ""),
    summary: String(formData.get("summary") ?? ""),
    estimatedHours: String(formData.get("estimatedHours") ?? ""),
    priority: String(formData.get("priority") ?? ""),
  }
  const errors: TaskFormState["errors"] = {}
  const estimatedHours = Number(values.estimatedHours)

  if (!values.title.trim()) {
    errors.title = "タスク名を入力してください。"
  }
  if (!values.estimatedHours || !Number.isFinite(estimatedHours) || estimatedHours <= 0) {
    errors.estimatedHours = "工数には0より大きい数値を入力してください。"
  }
  if (!priorities.includes(values.priority as (typeof priorities)[number])) {
    errors.priority = "優先順位を選択してください。"
  }

  if (Object.keys(errors).length > 0) {
    return { errors, values }
  }

  redirect(`/checklists/${checklistId}`)
}
