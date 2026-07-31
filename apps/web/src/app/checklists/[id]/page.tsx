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
import { findChecklistById } from "@/lib/checklist-mocks"

export default async function ChecklistDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params
  const checklist = findChecklistById(id)

  if (!checklist) {
    notFound()
  }

  return (
    <main className="min-h-screen bg-background px-6 py-12">
      <div className="mx-auto max-w-5xl">
        <div className="flex items-start justify-between gap-6">
          <div>
            <p className="text-sm font-semibold tracking-wide text-primary">CHECKLISTS</p>
            <h1 className="mt-2 text-3xl font-bold tracking-tight text-foreground">
              {checklist.name}
            </h1>
          </div>
          <Button asChild>
            <Link href={`/checklists/${checklist.id}/edit`}>編集</Link>
          </Button>
        </div>

        <section className="mt-8 rounded-xl border border-border bg-card p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-card-foreground">基本情報</h2>
          <dl className="mt-5 space-y-4">
            <div>
              <dt className="text-sm font-medium text-muted-foreground">名称</dt>
              <dd className="mt-1 text-base text-card-foreground">{checklist.name}</dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-muted-foreground">説明</dt>
              <dd className="mt-1 leading-6 text-card-foreground">{checklist.description}</dd>
            </div>
          </dl>
        </section>

        <section className="mt-8 rounded-xl border border-border bg-card p-6 shadow-sm" aria-labelledby="tasks-heading">
          <h2 id="tasks-heading" className="text-lg font-semibold text-card-foreground">
            タスク一覧
          </h2>
          {checklist.tasks.length === 0 ? (
            <p className="mt-5 text-sm text-muted-foreground">タスクはまだ登録されていません</p>
          ) : (
            <div className="mt-5">
              <Table className="min-w-[700px]">
                <TableHeader>
                  <TableRow>
                    <TableHead>タイトル</TableHead>
                    <TableHead>概要</TableHead>
                    <TableHead>工数</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {checklist.tasks.map((task) => (
                    <TableRow key={task.id}>
                      <TableCell className="font-medium text-card-foreground">{task.title}</TableCell>
                      <TableCell className="whitespace-normal text-muted-foreground">{task.summary}</TableCell>
                      <TableCell>{task.estimatedHours}時間</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </section>

        <Button asChild variant="outline" className="mt-8">
          <Link href="/">一覧へ戻る</Link>
        </Button>
      </div>
    </main>
  )
}
