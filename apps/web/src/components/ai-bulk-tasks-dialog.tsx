"use client"

import { useRef, useState, type ChangeEvent, type FormEvent } from "react"

import { AppDialog } from "@/components/app-dialog"
import { Button } from "@/components/ui/button"

const MAX_DESCRIPTION_LENGTH = 10_000
const MAX_FILE_SIZE = 10 * 1024 * 1024
const acceptedExtensions = ["pdf", "xlsx", "csv", "txt"]

export type AIBulkTask = {
  id: number
  checklist_id: number
  title: string
  summary: string
  estimated_hours: number
}

type AIBulkTasksDialogProps = {
  checklistId: number
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess: (tasks: AIBulkTask[]) => void
}

function formatFileSize(bytes: number) {
  return `${(bytes / 1024 / 1024).toFixed(1)} MiB`
}

function errorMessageForStatus(status: number, code: unknown) {
  switch (status) {
    case 404:
      return "指定したチェックリストが見つかりません。"
    case 413:
      return "ファイルサイズは10 MiB以下にしてください。"
    case 415:
      return "PDF、XLSX、CSV、TXT形式のファイルを選択してください。"
    case 422:
      return "入力内容またはファイルを確認してください。"
    case 502:
    case 503:
      return code === "upstream_error"
        ? "AI連携で問題が発生しました。時間をおいて再試行してください。"
        : "AIタスクの登録に失敗しました。時間をおいて再試行してください。"
    default:
      return "AIタスクの登録に失敗しました。時間をおいて再試行してください。"
  }
}

export function AIBulkTasksDialog({ checklistId, open, onOpenChange, onSuccess }: AIBulkTasksDialogProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [description, setDescription] = useState("")
  const [file, setFile] = useState<File | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const reset = () => {
    setDescription("")
    setFile(null)
    setError(null)
    if (inputRef.current) inputRef.current.value = ""
  }

  const handleOpenChange = (nextOpen: boolean) => {
    if (!nextOpen && !isSubmitting) {
      reset()
      onOpenChange(false)
      return
    }
    if (nextOpen) onOpenChange(true)
  }

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const selected = event.target.files?.[0]
    if (!selected) return
    const extension = selected.name.split(".").pop()?.toLowerCase()
    if (!extension || !acceptedExtensions.includes(extension)) {
      setError("PDF、XLSX、CSV、TXT形式のファイルを選択してください。")
      event.target.value = ""
      return
    }
    if (selected.size > MAX_FILE_SIZE) {
      setError("ファイルサイズは10 MiB以下にしてください。")
      event.target.value = ""
      return
    }
    setFile(selected)
    setError(null)
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!description.trim() && !file) {
      setError("説明またはファイルを入力してください。")
      return
    }

    setIsSubmitting(true)
    setError(null)
    const formData = new FormData()
    formData.set("checklist_id", String(checklistId))
    if (description.trim()) formData.set("description", description)
    if (file) formData.set("file", file)

    try {
      const response = await fetch("/api/checklists/ai-bulk-tasks", { method: "POST", body: formData })
      const body: unknown = await response.json().catch(() => null)
      if (!response.ok) {
        const code = body && typeof body === "object" ? (body as { code?: unknown }).code : undefined
        setError(errorMessageForStatus(response.status, code))
        return
      }
      if (!body || typeof body !== "object" || !Array.isArray((body as { tasks?: unknown }).tasks)) {
        setError("AIタスクの登録に失敗しました。時間をおいて再試行してください。")
        return
      }
      onSuccess((body as { tasks: AIBulkTask[] }).tasks)
      reset()
      onOpenChange(false)
    } catch {
      setError("通信に失敗しました。ネットワーク接続を確認して再試行してください。")
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AppDialog
      open={open}
      onOpenChange={handleOpenChange}
      title="AIでタスクを一括登録"
      description="説明や資料をもとに、AIがタスクを作成します。"
      size="xl"
      closeDisabled={isSubmitting}
      footer={
        <>
          <Button type="button" variant="outline" onClick={() => handleOpenChange(false)} disabled={isSubmitting}>キャンセル</Button>
          <Button type="submit" form="ai-bulk-tasks-form" disabled={isSubmitting}>{isSubmitting ? "AIで登録中…" : "AIで登録"}</Button>
        </>
      }
    >
      <form id="ai-bulk-tasks-form" className="grid gap-5" onSubmit={handleSubmit}>
        <div className="grid gap-2">
          <label htmlFor="ai-bulk-description" className="font-medium">説明（任意）</label>
          <textarea
            id="ai-bulk-description"
            className="min-h-32 w-full rounded-lg border border-input bg-transparent p-3 outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
            value={description}
            maxLength={MAX_DESCRIPTION_LENGTH}
            onChange={(event) => setDescription(event.target.value)}
            disabled={isSubmitting}
            aria-describedby="ai-bulk-character-count"
            placeholder="作成したいタスクの内容や補足を入力してください"
          />
          <p id="ai-bulk-character-count" className="text-right text-sm text-muted-foreground" aria-live="polite">{description.length.toLocaleString()} / 10,000</p>
        </div>
        <div className="grid gap-2">
          <label htmlFor="ai-bulk-file" className="font-medium">資料ファイル（任意）</label>
          <p id="ai-bulk-file-help" className="text-sm text-muted-foreground">PDF、XLSX、CSV、TXT（単一ファイル、10 MiB以下）</p>
          <input ref={inputRef} id="ai-bulk-file" className="sr-only" type="file" accept=".pdf,.xlsx,.csv,.txt" onChange={handleFileChange} disabled={isSubmitting} aria-describedby="ai-bulk-file-help" tabIndex={-1} />
          {file ? (
            <div className="flex items-center justify-between gap-3 rounded-lg border p-3">
              <span className="min-w-0 truncate" aria-label={`選択ファイル: ${file.name}、${formatFileSize(file.size)}`}>{file.name}（{formatFileSize(file.size)}）</span>
              <div className="flex shrink-0 gap-2">
                <Button type="button" variant="outline" onClick={() => inputRef.current?.click()} disabled={isSubmitting}>変更</Button>
                <Button type="button" variant="ghost" onClick={() => { setFile(null); setError(null); if (inputRef.current) inputRef.current.value = "" }} disabled={isSubmitting}>削除</Button>
              </div>
            </div>
          ) : <Button type="button" variant="outline" className="w-fit" onClick={() => inputRef.current?.click()} disabled={isSubmitting}>ファイルを選択</Button>}
        </div>
        {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      </form>
    </AppDialog>
  )
}
