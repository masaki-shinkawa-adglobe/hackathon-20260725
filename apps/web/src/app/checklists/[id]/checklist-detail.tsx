"use client"

import Link from "next/link"
import { useCallback, useEffect, useState } from "react"
import { toast } from "sonner"

import { AIBulkTasksDialog, type AIBulkTask } from "@/components/ai-bulk-tasks-dialog"
import { ManualTaskDialog } from "@/components/manual-task-dialog"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { ChecklistDeleteDialog } from "./checklist-delete-dialog"

type Task = {
  id: number
  checklist_id: number
  title: string
  summary: string | null
  estimated_hours: number
}

type Checklist = {
  id: number
  name: string
  description: string | null
  tasks: Task[]
}

type ChecklistDetailProps = {
  checklistId: string
}

const errorMessage = "チェックリストを取得できませんでした。時間をおいて再試行してください。"

export function ChecklistDetail({ checklistId }: ChecklistDetailProps) {
  const [checklist, setChecklist] = useState<Checklist | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [hasError, setHasError] = useState(false)
  const [isAIBulkTasksDialogOpen, setIsAIBulkTasksDialogOpen] = useState(false)
  const [isManualTaskDialogOpen, setIsManualTaskDialogOpen] = useState(false)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [hasRefreshError, setHasRefreshError] = useState(false)

  const loadChecklist = useCallback(async ({ preserveOnError = false, showRefreshError = false } = {}): Promise<boolean> => {
    if (!preserveOnError) {
      setIsLoading(true)
      setHasError(false)
    } else {
      setIsRefreshing(true)
      if (showRefreshError) setHasRefreshError(false)
    }

    try {
      const response = await fetch(`/api/checklists/${encodeURIComponent(checklistId)}`)
      if (!response.ok) throw new Error("Failed to fetch checklist")
      setChecklist((await response.json()) as Checklist)
      setHasRefreshError(false)
      return true
    } catch {
      if (!preserveOnError) {
        setChecklist(null)
        setHasError(true)
      } else if (showRefreshError) {
        setHasRefreshError(true)
      }
      return false
    } finally {
      if (!preserveOnError) {
        setIsLoading(false)
      } else {
        setIsRefreshing(false)
      }
    }
  }, [checklistId])

  const handleAIBulkTasksSuccess = async (tasks: AIBulkTask[]) => {
    toast.success(`${tasks.length}件のタスクを登録しました`)
    const didRefresh = await loadChecklist({ preserveOnError: true })
    if (!didRefresh) {
      toast.warning("登録は完了しましたが、一覧を更新できませんでした。画面を再読み込みしてください")
    }
  }

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void loadChecklist()
    }, 0)

    return () => window.clearTimeout(timeoutId)
  }, [loadChecklist])

  return (
    <main className="min-h-screen bg-background px-4 py-10 sm:px-6 sm:py-16">
      <div className="mx-auto max-w-5xl">
        {isLoading && (
          <p className="text-sm text-muted-foreground" role="status">
            読み込み中...
          </p>
        )}

        {hasError && (
          <section
            className="rounded-lg border border-destructive/30 bg-card p-6 text-card-foreground"
            role="alert"
          >
            <p className="text-sm text-destructive">{errorMessage}</p>
            <Button className="mt-4" onClick={() => void loadChecklist()}>
              再試行
            </Button>
          </section>
        )}

        {checklist && !isLoading && !hasError && (
          <>
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-sm font-semibold tracking-wide text-primary">CHECKLISTS</p>
                <h1 className="mt-2 text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
                  {checklist.name}
                </h1>
                <p className="mt-3 max-w-3xl whitespace-pre-wrap text-sm leading-6 text-muted-foreground sm:text-base">
                  {checklist.description || "説明はありません。"}
                </p>
              </div>
              <Button asChild variant="outline">
                <Link href={`/checklists/${checklist.id}/edit`}>編集する</Link>
              </Button>
              <ChecklistDeleteDialog checklistId={checklist.id} />
            </div>

            <section className="mt-10" aria-labelledby="task-list-heading">
              <div className="flex items-center justify-between gap-4">
                <h2 id="task-list-heading" className="text-xl font-semibold text-foreground">
                  タスク
                </h2>
                <div className="flex items-center gap-3">
                  <span className="text-sm text-muted-foreground">{checklist.tasks.length}件</span>
                  <Button onClick={() => setIsAIBulkTasksDialogOpen(true)}>AIでタスクを一括登録</Button>
                  <ManualTaskDialog
                    checklistId={checklist.id}
                    open={isManualTaskDialogOpen}
                    onOpenChange={setIsManualTaskDialogOpen}
                    onSuccess={() => loadChecklist({ preserveOnError: true, showRefreshError: true })}
                    trigger={<Button type="button">タスク手動登録</Button>}
                  />
                </div>
              </div>
              {hasRefreshError && (
                <div className="mt-4 rounded-lg border border-destructive/30 bg-card p-4" role="alert">
                  <p className="text-sm text-destructive">タスクは登録されましたが、一覧を更新できませんでした。</p>
                  <Button className="mt-3" variant="outline" onClick={() => void loadChecklist({ preserveOnError: true, showRefreshError: true })} disabled={isRefreshing}>
                    一覧を再取得
                  </Button>
                </div>
              )}
              {isRefreshing && <p className="mt-4 text-sm text-muted-foreground" role="status">タスク一覧を更新中...</p>}
              {checklist.tasks.length === 0 ? (
                <p className="mt-4 rounded-lg border border-dashed border-border bg-muted/40 px-4 py-8 text-center text-sm text-muted-foreground">
                  タスクはまだ登録されていません
                </p>
              ) : (
                <div className="mt-4 rounded-lg border border-border bg-card">
                  <Table className="min-w-[640px]">
                    <TableHeader>
                      <TableRow>
                        <TableHead scope="col">タイトル</TableHead>
                        <TableHead scope="col">概要</TableHead>
                        <TableHead scope="col" className="text-right">
                          工数
                        </TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {checklist.tasks.map((task) => (
                        <TableRow key={task.id}>
                          <TableCell className="font-medium text-foreground">
                            <Link
                              href={`/checklists/${checklist.id}/tasks/${task.id}`}
                              className="hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                            >
                              {task.title}
                            </Link>
                          </TableCell>
                          <TableCell className="whitespace-normal text-muted-foreground">
                            {task.summary || "—"}
                          </TableCell>
                          <TableCell className="text-right">
                            {task.estimated_hours}時間
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </section>

            <AIBulkTasksDialog
              checklistId={checklist.id}
              open={isAIBulkTasksDialogOpen}
              onOpenChange={setIsAIBulkTasksDialogOpen}
              onSuccess={handleAIBulkTasksSuccess}
            />
          </>
        )}

        <div className="mt-10">
          <Button asChild variant="link" className="px-0">
            <Link href="/">チェックリスト一覧へ戻る</Link>
          </Button>
        </div>
      </div>
    </main>
  )
}
