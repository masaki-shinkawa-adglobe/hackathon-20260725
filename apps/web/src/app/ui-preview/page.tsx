"use client"

import { useMemo, useState } from "react"

import { AppBreadcrumb } from "@/components/app-breadcrumb"
import { AIBulkTasksDialog, type AIBulkTask } from "@/components/ai-bulk-tasks-dialog"
import { BacklogTicketDialog, type BacklogTicketDialogSubmitValues } from "@/components/backlog-ticket-dialog"
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
import { toast } from "sonner"

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

const backlogPreviewTasks = [
  { id: "1", title: "売上データの締め処理" },
  { id: "2", title: "請求書の照合" },
  { id: "3", title: "未払費用の計上" },
  { id: "4", title: "固定資産の確認" },
  { id: "5", title: "月次レポート作成" },
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

const toastVariants = [
  {
    type: "default",
    show: () => toast("既定の通知", { description: "通常の処理結果をお知らせします。" }),
  },
  {
    type: "success",
    show: () => toast.success("成功通知", { description: "処理が正常に完了しました。" }),
  },
  {
    type: "info",
    show: () => toast.info("情報通知", { description: "確認が必要な情報があります。" }),
  },
  {
    type: "warning",
    show: () => toast.warning("警告通知", { description: "内容を確認してから続行してください。" }),
  },
  {
    type: "error",
    show: () => toast.error("エラー通知", { description: "処理を完了できませんでした。" }),
  },
  {
    type: "loading",
    show: () => toast.loading("処理中通知", { description: "処理が完了するまでお待ちください。" }),
  },
] as const

export default function UiPreviewPage() {
  const [searchValue, setSearchValue] = useState("")
  const [sort, setSort] = useState<DataTableSortState | null>(null)
  const [tableState, setTableState] = useState<TableState>("default")
  const [toastActionResult, setToastActionResult] = useState("アクション結果はありません。")
  const [checklistId, setChecklistId] = useState("1")
  const [isAIBulkTasksDialogOpen, setIsAIBulkTasksDialogOpen] = useState(false)
  const [createdTasks, setCreatedTasks] = useState<AIBulkTask[]>([])
  const [isBacklogTicketDialogOpen, setIsBacklogTicketDialogOpen] = useState(false)
  const [backlogTicketValues, setBacklogTicketValues] = useState<BacklogTicketDialogSubmitValues | null>(null)

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
    <SidebarProvider className="flex min-h-screen bg-background text-foreground [&>[data-slot=sidebar-wrapper]]:contents">
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
            <div>
              <h2 className="text-lg font-semibold">Backlogチケット発行</h2>
              <p className="text-sm text-muted-foreground">Backlog連携前の発行設定モーダルを確認します。</p>
            </div>
            <Button onClick={() => setIsBacklogTicketDialogOpen(true)}>Backlogチケット発行を開く</Button>
            {backlogTicketValues && <output aria-live="polite" className="block rounded-lg bg-muted p-3 text-sm">開始日: {backlogTicketValues.startDate}、終了日: {backlogTicketValues.endDate}、想定担当者数: {backlogTicketValues.expectedAssigneeCount}人、選択タスク: {backlogTicketValues.taskIds.join(", ")}</output>}
            <BacklogTicketDialog
              tasks={backlogPreviewTasks}
              initialStartDate="2025-06-01"
              initialEndDate="2025-06-30"
              initialExpectedAssigneeCount={3}
              initialSelectedTaskIds={backlogPreviewTasks.map((task) => task.id)}
              open={isBacklogTicketDialogOpen}
              onClose={() => setIsBacklogTicketDialogOpen(false)}
              onSubmit={setBacklogTicketValues}
            />
          </section>

          <section className="space-y-4 rounded-xl border bg-card p-6 text-card-foreground shadow-sm">
            <div>
              <h2 className="text-lg font-semibold">Sonner</h2>
              <p className="text-sm text-muted-foreground">通知の種類、アクション、非同期処理の状態更新を確認します。</p>
            </div>
            <div className="flex flex-wrap gap-3" aria-label="Toastの種類">
              {toastVariants.map(({ type, show }) => (
                <Button key={type} variant="outline" onClick={show}>
                  {type} Toast
                </Button>
              ))}
            </div>
            <div className="flex flex-wrap gap-3">
              <Button
                variant="outline"
                onClick={() =>
                  toast("変更を保存しました", {
                    description: "必要に応じて直前の状態へ戻せます。",
                    action: {
                      label: "元に戻す",
                      onClick: () => setToastActionResult("変更を元に戻しました。"),
                    },
                  })
                }
              >
                アクション付きToast
              </Button>
              <Button
                variant="outline"
                onClick={() =>
                  toast.promise(
                    new Promise<void>((resolve) => window.setTimeout(resolve, 500)),
                    {
                      loading: "処理を実行しています",
                      success: "処理が完了しました",
                      error: "処理に失敗しました",
                    }
                  )
                }
              >
                Promise成功Toast
              </Button>
              <Button
                variant="outline"
                onClick={() =>
                  toast.promise(
                    new Promise<void>((_, reject) => window.setTimeout(() => reject(new Error("失敗")), 500)),
                    {
                      loading: "処理を実行しています",
                      success: "処理が完了しました",
                      error: "処理に失敗しました",
                    }
                  )
                }
              >
                Promise失敗Toast
              </Button>
            </div>
            <p aria-live="polite" className="text-sm text-muted-foreground">
              {toastActionResult}
            </p>
          </section>

          <section className="space-y-4 rounded-xl border bg-card p-6 text-card-foreground shadow-sm">
            <div>
              <h2 className="text-lg font-semibold">AIでタスクを一括登録</h2>
              <p className="text-sm text-muted-foreground">実APIへ送信するモーダルの動作を確認します。</p>
            </div>
            <div className="flex items-end gap-3">
              <label className="grid gap-1 text-sm font-medium" htmlFor="preview-checklist-id">
                チェックリストID
                <Input id="preview-checklist-id" type="number" min="1" value={checklistId} onChange={(event) => setChecklistId(event.target.value)} />
              </label>
              <Button onClick={() => setIsAIBulkTasksDialogOpen(true)} disabled={!Number.isInteger(Number(checklistId)) || Number(checklistId) < 1}>AIでタスクを一括登録</Button>
            </div>
            {createdTasks.length > 0 && (
              <div aria-live="polite">
                <h3 className="font-medium">作成されたタスク</h3>
                <ul className="mt-2 list-disc pl-5">
                  {createdTasks.map((task) => <li key={task.id}>{task.title}</li>)}
                </ul>
              </div>
            )}
            <AIBulkTasksDialog
              checklistId={Number(checklistId)}
              open={isAIBulkTasksDialogOpen}
              onOpenChange={setIsAIBulkTasksDialogOpen}
              onSuccess={setCreatedTasks}
            />
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
