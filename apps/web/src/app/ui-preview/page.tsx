"use client"

import { useState } from "react"

import { AppDialog, type AppDialogSize } from "@/components/app-dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

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
      trigger={<Button>サイズ: {size}</Button>}
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
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl items-center px-6 py-16">
      <section className="w-full space-y-6 rounded-xl border bg-card p-6 text-card-foreground shadow-sm">
        <div className="space-y-2">
          <h1 className="text-2xl font-semibold">AppDialog プレビュー</h1>
          <p className="text-sm text-muted-foreground">
            各ボタンでサイズとアクセシビリティ操作を確認できます。
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <PreviewDialog size="sm" description="任意の説明を表示する例です。" />
          <PreviewDialog size="md" description="標準サイズの例です。" />
          <PreviewDialog size="lg" />
        </div>
      </section>
    </main>
  )
}
