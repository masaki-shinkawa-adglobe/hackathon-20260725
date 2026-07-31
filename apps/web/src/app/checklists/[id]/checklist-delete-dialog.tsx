"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { toast } from "sonner"

import { AppDialog } from "@/components/app-dialog"
import { Button } from "@/components/ui/button"

type ChecklistDeleteDialogProps = {
  checklistId: number
}

const deleteErrorMessage = "チェックリストの削除に失敗しました。時間をおいて再試行してください。"

export function ChecklistDeleteDialog({ checklistId }: ChecklistDeleteDialogProps) {
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)

  const handleOpenChange = (nextOpen: boolean) => {
    if (!isDeleting) setOpen(nextOpen)
  }

  const handleDelete = async () => {
    if (isDeleting) return

    setIsDeleting(true)
    try {
      const response = await fetch(`/api/checklists/${encodeURIComponent(checklistId)}`, { method: "DELETE" })
      if (response.status !== 204) {
        toast.error(deleteErrorMessage)
        return
      }

      toast.success("チェックリストを削除しました。")
      router.push("/")
    } catch {
      toast.error(deleteErrorMessage)
    } finally {
      setIsDeleting(false)
    }
  }

  return (
    <AppDialog
      open={open}
      onOpenChange={handleOpenChange}
      trigger={<Button variant="destructive">削除する</Button>}
      title="チェックリストを削除しますか？"
      description="この操作は取り消せません。"
      closeDisabled={isDeleting}
      footer={
        <>
          <Button type="button" variant="outline" onClick={() => handleOpenChange(false)} disabled={isDeleting}>
            キャンセル
          </Button>
          <Button type="button" variant="destructive" onClick={handleDelete} disabled={isDeleting}>
            {isDeleting ? "削除中…" : "削除する"}
          </Button>
        </>
      }
    >
      <p className="text-sm text-muted-foreground">
        このチェックリストに含まれるローカルタスクも削除されます。Backlog上の課題は削除されません。
      </p>
    </AppDialog>
  )
}
