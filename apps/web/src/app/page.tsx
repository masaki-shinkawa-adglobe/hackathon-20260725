"use client"

import * as React from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { PlusIcon } from "lucide-react"

import { AppBreadcrumb } from "@/components/app-breadcrumb"
import { AppSidebar } from "@/components/app-sidebar"
import {
  DataTable,
  type DataTableColumn,
} from "@/components/data-table"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar"

type Checklist = {
  id: string
  name: string
  taskCount: number
  backlogLastRegisteredAt: string
  updatedAt: string
}

const checklists: Checklist[] = [
  {
    id: "business-trip",
    name: "出張の準備",
    taskCount: 6,
    backlogLastRegisteredAt: "2026年7月30日 13:45",
    updatedAt: "2026年7月30日 14:30",
  },
  {
    id: "new-employee",
    name: "新入社員の受け入れ",
    taskCount: 8,
    backlogLastRegisteredAt: "2026年7月29日 09:50",
    updatedAt: "2026年7月29日 10:15",
  },
  {
    id: "monthly-closing",
    name: "月次締め作業",
    taskCount: 5,
    backlogLastRegisteredAt: "2026年7月28日 16:30",
    updatedAt: "2026年7月28日 17:45",
  },
]

const columns: DataTableColumn<Checklist>[] = [
  {
    id: "name",
    header: "チェックリスト名",
    cell: (checklist) => (
      <Link
        href={`/checklists/${checklist.id}`}
        className="font-medium text-foreground underline-offset-4 hover:underline focus-visible:underline"
      >
        {checklist.name}
      </Link>
    ),
  },
  {
    id: "taskCount",
    header: "登録タスク数",
    cell: (checklist) => (
      <span className="block text-right tabular-nums">{checklist.taskCount}</span>
    ),
  },
  {
    id: "backlogLastRegisteredAt",
    header: "Backlog最終登録日時",
    cell: (checklist) => (
      <span className="text-muted-foreground">
        {checklist.backlogLastRegisteredAt}
      </span>
    ),
  },
  {
    id: "updatedAt",
    header: "最終更新日時",
    cell: (checklist) => (
      <span className="text-muted-foreground">{checklist.updatedAt}</span>
    ),
  },
]

export default function Home() {
  const router = useRouter()
  const [searchQuery, setSearchQuery] = React.useState("")
  const [searchInputValue, setSearchInputValue] = React.useState("")

  React.useEffect(() => {
    const timer = setTimeout(() => {
      setSearchQuery(searchInputValue)
    }, 300)

    return () => clearTimeout(timer)
  }, [searchInputValue])

  const normalizedQuery = searchQuery.trim().toLocaleLowerCase("ja-JP")
  const filteredChecklists = checklists.filter((checklist) =>
    checklist.name.toLocaleLowerCase("ja-JP").includes(normalizedQuery)
  )

  return (
    <SidebarProvider className="bg-muted/30">
      <AppSidebar />
      <SidebarInset className="min-h-svh bg-transparent">
        <main className="w-full px-12 py-8">
          <div className="flex items-center justify-between gap-6">
            <AppBreadcrumb items={[{ label: "チェックリスト一覧" }]} />
            <Button
              asChild
              variant="outline"
              className="h-12 w-40 border-orange-500 text-base font-semibold text-orange-600 hover:border-orange-600 hover:bg-orange-50 hover:text-orange-700"
            >
              <Link href="/checklists/new">
                <PlusIcon aria-hidden="true" className="size-5" />
                新規作成
              </Link>
            </Button>
          </div>

          <section
            className="mt-6 rounded-xl border border-border bg-card p-8 shadow-sm"
            aria-labelledby="checklist-search-heading"
          >
            <label
              id="checklist-search-heading"
              className="grid max-w-xl gap-3 text-base font-semibold text-foreground"
              htmlFor="checklist-search"
            >
              キーワード
              <Input
                id="checklist-search"
                type="search"
                value={searchInputValue}
                placeholder="チェックリスト名で検索"
                onChange={(event) => setSearchInputValue(event.target.value)}
                aria-label="検索"
                className="h-15 px-4 text-base"
              />
            </label>
          </section>

          <section
            className="mt-6 overflow-hidden rounded-xl border border-border bg-card shadow-sm [&>div]:space-y-0 [&_table]:border-collapse [&_table]:text-base [&_thead]:bg-muted/50 [&_th]:h-16 [&_th]:px-6 [&_th]:text-sm [&_th]:font-semibold [&_th]:text-muted-foreground [&_td]:px-6 [&_td]:py-6 [&_tbody_tr:last-child]:border-b-0"
            aria-labelledby="checklist-table-heading"
          >
            <h1 id="checklist-table-heading" className="sr-only">
              チェックリスト一覧
            </h1>
            <DataTable
              columns={columns}
              data={filteredChecklists}
              getRowKey={(checklist) => checklist.id}
              onRowClick={(checklist) =>
                router.push(`/checklists/${checklist.id}`)
              }
              emptyMessage="該当するチェックリストがありません。"
            />
          </section>
          <p aria-live="polite" className="mt-5 text-base font-semibold text-foreground">
            全 {filteredChecklists.length} 件
          </p>
        </main>
      </SidebarInset>
    </SidebarProvider>
  )
}
