"use client"

import * as React from "react"

import {
  DataTable,
  type DataTableColumn,
} from "@/components/data-table"

type Checklist = {
  id: string
  name: string
  description: string
  completedItemCount: number
  totalItemCount: number
  updatedAt: string
}

const checklists: Checklist[] = [
  {
    id: "business-trip",
    name: "出張の準備",
    description: "来週の大阪出張に必要な持ち物と手配を確認します。",
    completedItemCount: 4,
    totalItemCount: 6,
    updatedAt: "2026年7月30日 14:30",
  },
  {
    id: "new-employee",
    name: "新入社員の受け入れ",
    description: "入社初日に必要なアカウント発行と備品準備の一覧です。",
    completedItemCount: 7,
    totalItemCount: 8,
    updatedAt: "2026年7月29日 10:15",
  },
  {
    id: "monthly-closing",
    name: "月次締め作業",
    description: "経費精算とレポート提出の進捗を管理します。",
    completedItemCount: 2,
    totalItemCount: 5,
    updatedAt: "2026年7月28日 17:45",
  },
]

const columns: DataTableColumn<Checklist>[] = [
  {
    id: "name",
    header: "チェックリスト名",
    cell: (checklist) => (
      <span className="font-medium text-foreground">{checklist.name}</span>
    ),
  },
  {
    id: "description",
    header: "説明",
    cell: (checklist) => (
      <span className="whitespace-normal text-muted-foreground">
        {checklist.description}
      </span>
    ),
  },
  {
    id: "completedItemCount",
    header: "完了済み項目数",
    cell: (checklist) => (
      <span className="block text-right tabular-nums">
        {checklist.completedItemCount}
      </span>
    ),
  },
  {
    id: "totalItemCount",
    header: "総項目数",
    cell: (checklist) => (
      <span className="block text-right tabular-nums">
        {checklist.totalItemCount}
      </span>
    ),
  },
  {
    id: "updatedAt",
    header: "更新日時",
    cell: (checklist) => (
      <span className="text-muted-foreground">{checklist.updatedAt}</span>
    ),
  },
]

export default function Home() {
  const [searchQuery, setSearchQuery] = React.useState("")
  const normalizedQuery = searchQuery.trim().toLocaleLowerCase("ja-JP")
  const filteredChecklists = checklists.filter((checklist) =>
    [checklist.name, checklist.description].some((value) =>
      value.toLocaleLowerCase("ja-JP").includes(normalizedQuery)
    )
  )

  return (
    <main className="min-h-screen bg-muted/30 px-10 py-14">
      <div className="mx-auto w-full max-w-6xl">
        <p className="text-sm font-semibold tracking-widest text-muted-foreground uppercase">
          Checklists
        </p>
        <h1 className="mt-3 text-4xl font-bold tracking-tight text-foreground">
          チェックリスト一覧
        </h1>
        <p className="mt-4 text-base text-muted-foreground">
          保存したチェックリストの進捗を確認できます。
        </p>

        <section
          className="mt-8 overflow-hidden rounded-xl border bg-card p-4 shadow-sm"
          aria-labelledby="checklist-table-heading"
        >
          <h2 id="checklist-table-heading" className="sr-only">
            チェックリスト一覧
          </h2>
          <DataTable
            columns={columns}
            data={filteredChecklists}
            getRowKey={(checklist) => checklist.id}
            search={{
              value: searchQuery,
              columns: ["name", "description"],
              placeholder: "チェックリスト名または説明で検索",
              onChange: (value) => setSearchQuery(value),
            }}
            emptyMessage="該当するチェックリストがありません。"
          />
        </section>
      </div>
    </main>
  )
}
