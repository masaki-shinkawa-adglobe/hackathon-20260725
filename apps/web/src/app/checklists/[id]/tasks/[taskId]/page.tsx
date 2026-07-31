import { notFound } from "next/navigation"

import { AppBreadcrumb } from "@/components/app-breadcrumb"
import { AppSidebar } from "@/components/app-sidebar"
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar"
import { findTaskByChecklistIdAndTaskId } from "@/lib/checklist-mock-data"

import { TaskForm } from "./task-form"

type TaskDetailPageProps = {
  params: Promise<{ id: string; taskId: string }>
}

export default async function TaskDetailPage({ params }: TaskDetailPageProps) {
  const { id, taskId } = await params
  const result = findTaskByChecklistIdAndTaskId(id, taskId)

  if (!result) {
    notFound()
  }

  const { checklist, task } = result

  return (
    <SidebarProvider className="bg-muted/30">
      <AppSidebar />
      <SidebarInset className="min-h-svh bg-transparent">
        <div className="mx-auto w-full max-w-4xl px-10 py-8">
          <AppBreadcrumb
            items={[
              { label: "チェックリスト", href: "/" },
              { label: checklist.name, href: `/checklists/${checklist.id}` },
              { label: task.title },
            ]}
          />

          <div className="mt-8">
            <h1 className="text-2xl font-bold tracking-tight text-foreground">タスクを編集</h1>
            <p className="mt-2 text-sm text-muted-foreground">
              タスクの内容、工数、優先順位を更新できます。
            </p>
          </div>

          <section className="mt-8 rounded-xl border border-border bg-card p-6 shadow-sm" aria-labelledby="task-form-heading">
            <h2 id="task-form-heading" className="text-lg font-semibold">{task.title}</h2>
            <div className="mt-6">
              <TaskForm
                checklistId={checklist.id}
                taskId={task.id}
                initialValues={{
                  title: task.title,
                  summary: task.summary,
                  estimatedHours: String(task.estimatedHours),
                  priority: task.priority ?? "medium",
                }}
              />
            </div>
          </section>
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}
