"use client"

import Link from "next/link"
import { useActionState } from "react"
import { useFormStatus } from "react-dom"

import { Button } from "@/components/ui/button"

import { updateTask, type TaskFormState } from "./actions"

type TaskFormProps = {
  checklistId: string
  taskId: string
  initialValues: TaskFormState["values"]
}

function SubmitButton() {
  const { pending } = useFormStatus()

  return (
    <Button type="submit" disabled={pending}>
      {pending ? "保存中..." : "保存する"}
    </Button>
  )
}

function TaskFields({ state }: { state: TaskFormState }) {
  const { pending } = useFormStatus()

  return (
    <>
      <div className="grid gap-2">
        <label htmlFor="title" className="text-sm font-medium">
          タスク名
        </label>
        <input
          id="title"
          name="title"
          type="text"
          required
          disabled={pending}
          defaultValue={state.values.title}
          aria-invalid={Boolean(state.errors.title)}
          aria-describedby={state.errors.title ? "title-error" : undefined}
          className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/50"
        />
        {state.errors.title && <p id="title-error" className="text-sm text-destructive">{state.errors.title}</p>}
      </div>

      <div className="grid gap-2">
        <label htmlFor="summary" className="text-sm font-medium">本文</label>
        <textarea
          id="summary"
          name="summary"
          rows={6}
          disabled={pending}
          defaultValue={state.values.summary}
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/50"
        />
      </div>

      <div className="grid grid-cols-2 gap-5">
        <div className="grid gap-2">
          <label htmlFor="estimatedHours" className="text-sm font-medium">工数（時間）</label>
          <input
            id="estimatedHours"
            name="estimatedHours"
            type="number"
            step="any"
            required
            disabled={pending}
            defaultValue={state.values.estimatedHours}
            aria-invalid={Boolean(state.errors.estimatedHours)}
            aria-describedby={state.errors.estimatedHours ? "estimated-hours-error" : undefined}
            className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/50"
          />
          {state.errors.estimatedHours && <p id="estimated-hours-error" className="text-sm text-destructive">{state.errors.estimatedHours}</p>}
        </div>

        <div className="grid gap-2">
          <label htmlFor="priority" className="text-sm font-medium">優先順位</label>
          <select
            id="priority"
            name="priority"
            required
            disabled={pending}
            defaultValue={state.values.priority}
            aria-invalid={Boolean(state.errors.priority)}
            aria-describedby={state.errors.priority ? "priority-error" : undefined}
            className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/50"
          >
            <option value="low">低</option>
            <option value="medium">中</option>
            <option value="high">高</option>
          </select>
          {state.errors.priority && <p id="priority-error" className="text-sm text-destructive">{state.errors.priority}</p>}
        </div>
      </div>
    </>
  )
}

export function TaskForm({ checklistId, taskId, initialValues }: TaskFormProps) {
  const [state, formAction] = useActionState(
    updateTask.bind(null, checklistId, taskId),
    { errors: {}, values: initialValues }
  )

  return (
    <form action={formAction} className="space-y-6" noValidate>
      <TaskFields state={state} />

      <div className="flex justify-end gap-3 border-t border-border pt-6">
        <Button asChild variant="outline">
          <Link href={`/checklists/${checklistId}`}>キャンセル</Link>
        </Button>
        <SubmitButton />
      </div>
    </form>
  )
}
