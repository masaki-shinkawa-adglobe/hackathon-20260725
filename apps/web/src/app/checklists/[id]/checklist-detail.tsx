"use client"

import Link from "next/link"
import { useCallback, useEffect, useState } from "react"

import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

type Task = {
  id: number
  checklist_id: number
  title: string
  summary: string
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

  const loadChecklist = useCallback(async () => {
    setIsLoading(true)
    setHasError(false)

    try {
      const response = await fetch(`/api/checklists/${encodeURIComponent(checklistId)}`)
      if (!response.ok) throw new Error("Failed to fetch checklist")
      setChecklist((await response.json()) as Checklist)
    } catch {
      setChecklist(null)
      setHasError(true)
    } finally {
      setIsLoading(false)
    }
  }, [checklistId])

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void loadChecklist()
    }, 0)

    return () => window.clearTimeout(timeoutId)
  }, [loadChecklist])

  return (
    <main className="min-h-screen bg-muted/30 px-4 py-10 sm:px-6 sm:py-16">
      <div className="mx-auto max-w-4xl">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-sm font-semibold tracking-wide text-primary">CHECKLISTS</p>
            <h1 className="mt-2 text-3xl font-bold tracking-tight text-foreground sm:text-4xl">チェックリスト詳細</h1>
          </div>
          <Button asChild variant="outline">
            <Link href={`/checklists/${checklistId}/edit`}>編集</Link>
          </Button>
        </div>

        <div className="mt-6">
          <Link href="/" className="text-sm font-medium text-primary underline-offset-4 hover:underline">一覧へ戻る</Link>
        </div>

        {isLoading && <p className="mt-8 text-sm text-muted-foreground" role="status">読み込み中...</p>}

        {hasError && (
          <section className="mt-8 rounded-2xl border border-destructive/30 bg-card p-6 text-card-foreground shadow-sm" role="alert">
            <p className="text-sm text-destructive">{errorMessage}</p>
            <Button className="mt-4" onClick={() => void loadChecklist()}>再試行</Button>
          </section>
        )}

        {checklist && !isLoading && !hasError && (
          <>
            <section className="mt-8 rounded-2xl border border-border bg-card p-6 text-card-foreground shadow-sm">
              <h2 className="text-xl font-semibold">{checklist.name}</h2>
              <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-muted-foreground">{checklist.description || "説明はありません。"}</p>
            </section>

            <section className="mt-8 rounded-2xl border border-border bg-card p-6 text-card-foreground shadow-sm">
              <h2 className="text-lg font-semibold">タスク</h2>
              {checklist.tasks.length === 0 ? (
                <p className="mt-3 text-sm text-muted-foreground">登録されているタスクはありません。</p>
              ) : (
                <div className="mt-4">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead scope="col">タイトル</TableHead>
                        <TableHead scope="col">本文</TableHead>
                        <TableHead scope="col">工数</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {checklist.tasks.map((task) => (
                        <TableRow key={task.id}>
                          <TableCell className="font-medium">{task.title}</TableCell>
                          <TableCell className="whitespace-normal">{task.summary}</TableCell>
                          <TableCell>{task.estimated_hours}時間</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </section>
          </>
        )}
      </div>
    </main>
  )
}
