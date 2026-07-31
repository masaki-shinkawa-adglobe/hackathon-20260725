import Link from "next/link"
import { notFound } from "next/navigation"

import { Button } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { findChecklistById } from "@/lib/checklist-mock-data"

type ChecklistDetailPageProps = {
  params: Promise<{ id: string }>
}

export default async function ChecklistDetailPage({ params }: ChecklistDetailPageProps) {
  const { id } = await params
  const checklist = findChecklistById(id)

  if (!checklist) {
    notFound()
  }

  return (
    <main className="min-h-screen bg-background px-4 py-10 sm:px-6 sm:py-16">
      <div className="mx-auto max-w-5xl">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-sm font-semibold tracking-wide text-primary">CHECKLISTS</p>
            <h1 className="mt-2 text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
              {checklist.name}
            </h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-muted-foreground sm:text-base">
              {checklist.description}
            </p>
          </div>
          <Button asChild variant="outline">
            <Link href={`/checklists/${checklist.id}/edit`}>編集する</Link>
          </Button>
        </div>

        <section className="mt-10" aria-labelledby="task-list-heading">
          <div className="flex items-center justify-between gap-4">
            <h2 id="task-list-heading" className="text-xl font-semibold text-foreground">
              タスク
            </h2>
            <span className="text-sm text-muted-foreground">{checklist.tasks.length}件</span>
          </div>

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
                        {task.summary}
                      </TableCell>
                      <TableCell className="text-right">{task.estimatedHours}時間</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </section>

        <div className="mt-10">
          <Button asChild variant="link" className="px-0">
            <Link href="/">チェックリスト一覧へ戻る</Link>
          </Button>
        </div>
      </div>
    </main>
  )
}
