"use client"

import { useMemo, useState } from "react"

import { AppBreadcrumb } from "@/components/app-breadcrumb"
import { AppDialog, type AppDialogSize } from "@/components/app-dialog"
import { AppSidebar } from "@/components/app-sidebar"
import {
  DataTable,
  type DataTableColumn,
  type DataTableSortState,
} from "@/components/data-table"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { SidebarProvider } from "@/components/ui/sidebar"

type PreviewRow = {
  id: string
  name: string
  status: string
  updatedAt: string
}

type TableState = "default" | "loading" | "error" | "empty"

const previewRows: PreviewRow[] = [
  { id: "1", name: "出張準備", status: "進行中", updatedAt: "2026-07-30" },
  { id: "2", name: "イベント準備", status: "未着手", updatedAt: "2026-07-29" },
  { id: "3", name: "入社準備", status: "完了", updatedAt: "2026-07-28" },
]

const columns: DataTableColumn<PreviewRow>[] = [
  { id: "name", header: "チェックリスト", cell: (row) => row.name, sortable: true },
  { id: "status", header: "状態", cell: (row) => row.status },
  { id: "updatedAt", header: "更新日", cell: (row) => row.updatedAt, sortable: true },
]

type PreviewDialogProps = {
  size: AppDialogSize
  description?: string
}

function PreviewDialog({ size, description }: PreviewDialogProps) {
  const [open, setOpen] = useState(false)

  return (
    <AppDialog
      open={open}
      onOpenChange={setOpen}
      trigger={<Button variant="outline">サイズ: {size}</Button>}
      title="AppDialog プレビュー"
      description={description}
      footer={<Button onClick={() => setOpen(false)}>完了</Button>}
      size={size}
    >
      <div className="grid gap-4">
        <p className="text-sm text-muted-foreground">
          閉じるボタン、Escapeキー、背景クリックで閉じられます。Tabキーでフォーカスが循環し、閉じるとこのボタンへ戻ります。
        </p>
        <Input aria-label={`${size}の入力欄`} placeholder="入力欄" />
        <Button variant="outline">フォーカス確認用ボタン</Button>
      </div>
    </AppDialog>
  )
}

export default function UiPreviewPage() {
  const [searchValue, setSearchValue] = useState("")
  const [sort, setSort] = useState<DataTableSortState | null>(null)
  const [tableState, setTableState] = useState<TableState>("default")

  const data = useMemo(() => {
    if (tableState === "empty") {
      return []
    }

    const filteredRows = previewRows.filter((row) =>
      [row.name, row.status].some((value) =>
        value.toLocaleLowerCase().includes(searchValue.toLocaleLowerCase())
      )
    )

    if (!sort) {
      return filteredRows
    }

    return [...filteredRows].sort((left, right) => {
      const result = left[sort.columnId as keyof PreviewRow].localeCompare(
        right[sort.columnId as keyof PreviewRow],
        "ja"
      )
      return sort.direction === "asc" ? result : -result
    })
  }, [searchValue, sort, tableState])

  return (
    <SidebarProvider className="flex min-h-screen bg-background text-foreground">
      <AppSidebar />
      <div
        aria-hidden="true"
        className="hidden shrink-0 md:block md:w-64"
        data-testid="sidebar-offset"
      />
      <main className="min-h-screen flex-1 px-8 py-10">
        <div className="mx-auto max-w-6xl space-y-10">
          <AppBreadcrumb items={[{ label: "開発者向け" }, { label: "UIプレビュー" }]} />

          <section className="space-y-3">
            <h1 className="text-3xl font-semibold tracking-tight">共通UIプレビュー</h1>
            <p className="text-muted-foreground">
              業務画面へ組み込む前に、代表的な共通コンポーネントの見た目と操作を確認できます。
            </p>
          </section>

          <section className="space-y-4 rounded-xl border bg-card p-6 text-card-foreground shadow-sm">
            <div>
              <h2 className="text-lg font-semibold">Button</h2>
              <p className="text-sm text-muted-foreground">各バリアントの表示を確認します。</p>
            </div>
            <div className="flex flex-wrap gap-3">
              <Button>default</Button>
              <Button variant="outline">outline</Button>
              <Button variant="destructive">destructive</Button>
              <Button variant="ghost">ghost</Button>
            </div>
          </section>

          <section className="space-y-4 rounded-xl border bg-card p-6 text-card-foreground shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold">DataTable</h2>
                <p className="text-sm text-muted-foreground">検索、単一列ソート、各状態を確認します。</p>
              </div>
              <div className="flex flex-wrap gap-2" aria-label="DataTableの状態切替">
                <Button variant="outline" onClick={() => setTableState("default")}>通常</Button>
                <Button variant="outline" onClick={() => setTableState("loading")}>loading</Button>
                <Button variant="outline" onClick={() => setTableState("error")}>error</Button>
                <Button variant="outline" onClick={() => setTableState("empty")}>空データ</Button>
              </div>
            </div>
            <DataTable
              columns={columns}
              data={data}
              search={{
                value: searchValue,
                columns: ["name", "status"],
                placeholder: "チェックリスト名または状態で検索",
                onChange: setSearchValue,
              }}
              sort={{ value: sort, onChange: setSort }}
              loading={tableState === "loading"}
              error={tableState === "error" ? "データの取得に失敗しました。" : undefined}
              onRetry={() => setTableState("default")}
              emptyMessage="表示するチェックリストがありません。"
              getRowKey={(row) => row.id}
            />
          </section>

          <section className="space-y-4 rounded-xl border bg-card p-6 text-card-foreground shadow-sm">
            <div>
              <h2 className="text-lg font-semibold">AppDialog</h2>
              <p className="text-sm text-muted-foreground">サイズごとの開閉とフォーカス操作を確認します。</p>
            </div>
            <div className="flex flex-wrap gap-3">
              <PreviewDialog size="sm" description="任意の説明を表示する例です。" />
              <PreviewDialog size="md" description="標準サイズの例です。" />
              <PreviewDialog size="lg" />
            </div>
          </section>
        </div>
      </main>
    </SidebarProvider>
  )
}
