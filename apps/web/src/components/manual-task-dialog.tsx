"use client"

import { useState, type FormEvent, type ReactElement } from "react"
import { toast } from "sonner"

import { AppDialog } from "@/components/app-dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

type ManualTaskDialogProps = {
  checklistId: number
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess: () => Promise<boolean>
  trigger?: ReactElement
}

type FieldErrors = {
  title?: string
  estimatedHours?: string
}

function errorMessageForStatus(status: number) {
  if (status === 404) return "指定したチェックリストが見つかりません。"
  if (status === 422) return "入力内容を確認してください。"
  return "タスクの登録に失敗しました。時間をおいて再試行してください。"
}

function isTask(body: unknown): boolean {
  if (!body || typeof body !== "object") return false
  const task = body as { id?: unknown; checklist_id?: unknown; title?: unknown; summary?: unknown; estimated_hours?: unknown }
  return (
    typeof task.id === "number" &&
    typeof task.checklist_id === "number" &&
    typeof task.title === "string" &&
    (typeof task.summary === "string" || task.summary === null) &&
    typeof task.estimated_hours === "number" &&
    Number.isFinite(task.estimated_hours)
  )
}

export function ManualTaskDialog({ checklistId, open, onOpenChange, onSuccess, trigger }: ManualTaskDialogProps) {
  const [title, setTitle] = useState("")
  const [summary, setSummary] = useState("")
  const [estimatedHours, setEstimatedHours] = useState("")
  const [errors, setErrors] = useState<FieldErrors>({})
  const [isSubmitting, setIsSubmitting] = useState(false)

  const reset = () => {
    setTitle("")
    setSummary("")
    setEstimatedHours("")
    setErrors({})
  }

  const handleOpenChange = (nextOpen: boolean) => {
    if (nextOpen) {
      onOpenChange(true)
      return
    }
    if (!isSubmitting) {
      reset()
      onOpenChange(false)
    }
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const normalizedTitle = title.trim()
    const parsedEstimatedHours = Number(estimatedHours)
    const nextErrors: FieldErrors = {}

    if (!normalizedTitle || normalizedTitle.length > 255) {
      nextErrors.title = "タイトルは1〜255文字で入力してください。"
    }
    if (!estimatedHours.trim() || !Number.isFinite(parsedEstimatedHours) || parsedEstimatedHours <= 0) {
      nextErrors.estimatedHours = "工数は0より大きい数値で入力してください。"
    }
    if (Object.keys(nextErrors).length > 0) {
      setErrors(nextErrors)
      return
    }

    setIsSubmitting(true)
    setErrors({})
    try {
      const response = await fetch(`/api/checklists/${encodeURIComponent(String(checklistId))}/tasks`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: normalizedTitle,
          summary: summary.trim() || null,
          estimated_hours: parsedEstimatedHours,
        }),
      })
      const body: unknown = await response.json().catch(() => null)
      if (!response.ok) {
        toast.error(errorMessageForStatus(response.status))
        return
      }
      if (response.status !== 201 || !isTask(body)) {
        toast.error("タスクの登録に失敗しました。時間をおいて再試行してください。")
        return
      }

      const refreshed = await onSuccess()
      reset()
      onOpenChange(false)
      if (refreshed) {
        toast.success("タスクを登録しました。")
      } else {
        toast.error("タスクは登録されましたが、一覧を更新できませんでした。再取得してください。")
      }
    } catch {
      toast.error("通信に失敗しました。ネットワーク接続を確認して再試行してください。")
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AppDialog
      open={open}
      onOpenChange={handleOpenChange}
      trigger={trigger}
      title="タスク手動登録"
      description="タスクの内容と工数を入力してください。"
      closeDisabled={isSubmitting}
      footer={
        <>
          <Button type="button" variant="outline" onClick={() => handleOpenChange(false)} disabled={isSubmitting}>キャンセル</Button>
          <Button type="submit" form="manual-task-form" disabled={isSubmitting}>{isSubmitting ? "登録中…" : "登録する"}</Button>
        </>
      }
    >
      <form id="manual-task-form" className="grid gap-5" noValidate onSubmit={handleSubmit}>
        <div className="grid gap-2">
          <label htmlFor="manual-task-title" className="font-medium">タイトル</label>
          <Input
            id="manual-task-title"
            autoFocus
            required
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            disabled={isSubmitting}
            aria-invalid={Boolean(errors.title)}
            aria-describedby={errors.title ? "manual-task-title-error" : undefined}
          />
          {errors.title && <p id="manual-task-title-error" role="alert" className="text-sm text-destructive">{errors.title}</p>}
        </div>
        <div className="grid gap-2">
          <label htmlFor="manual-task-summary" className="font-medium">本文（任意）</label>
          <textarea
            id="manual-task-summary"
            className="min-h-28 w-full rounded-lg border border-input bg-transparent p-3 outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:pointer-events-none disabled:cursor-not-allowed disabled:bg-input/50 disabled:opacity-50"
            value={summary}
            onChange={(event) => setSummary(event.target.value)}
            disabled={isSubmitting}
          />
        </div>
        <div className="grid gap-2">
          <label htmlFor="manual-task-estimated-hours" className="font-medium">工数（時間）</label>
          <Input
            id="manual-task-estimated-hours"
            type="number"
            min="0"
            step="any"
            required
            value={estimatedHours}
            onChange={(event) => setEstimatedHours(event.target.value)}
            disabled={isSubmitting}
            aria-invalid={Boolean(errors.estimatedHours)}
            aria-describedby={errors.estimatedHours ? "manual-task-estimated-hours-error" : undefined}
          />
          {errors.estimatedHours && <p id="manual-task-estimated-hours-error" role="alert" className="text-sm text-destructive">{errors.estimatedHours}</p>}
        </div>
      </form>
    </AppDialog>
  )
}

export type { ManualTaskDialogProps }
