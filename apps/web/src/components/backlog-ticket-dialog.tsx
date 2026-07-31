"use client"

import { useState, type FormEvent } from "react"
import { MinusIcon, PlusIcon } from "lucide-react"

import { AppDialog } from "@/components/app-dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

export type BacklogTicketTask = {
  id: string
  title: string
}

export type BacklogTicketDialogSubmitValues = {
  startDate: string
  endDate: string
  expectedAssigneeCount: number
  taskIds: string[]
}

type BacklogTicketDialogProps = {
  tasks: BacklogTicketTask[]
  initialStartDate: string
  initialEndDate: string
  initialExpectedAssigneeCount: number
  initialSelectedTaskIds: string[]
  open: boolean
  onClose: () => void
  onSubmit: (values: BacklogTicketDialogSubmitValues) => void
}

function BacklogTicketDialog({
  tasks,
  initialStartDate,
  initialEndDate,
  initialExpectedAssigneeCount,
  initialSelectedTaskIds,
  open,
  onClose,
  onSubmit,
}: BacklogTicketDialogProps) {
  const [startDate, setStartDate] = useState(initialStartDate)
  const [endDate, setEndDate] = useState(initialEndDate)
  const [expectedAssigneeCount, setExpectedAssigneeCount] = useState(Math.max(1, initialExpectedAssigneeCount))
  const [selectedTaskIds, setSelectedTaskIds] = useState<string[]>(initialSelectedTaskIds)

  const reset = () => {
    setStartDate(initialStartDate)
    setEndDate(initialEndDate)
    setExpectedAssigneeCount(Math.max(1, initialExpectedAssigneeCount))
    setSelectedTaskIds(initialSelectedTaskIds)
  }

  const handleClose = () => {
    reset()
    onClose()
  }

  const isStartDateMissing = !startDate
  const isEndDateMissing = !endDate
  const isDateRangeInvalid = Boolean(startDate && endDate && startDate > endDate)
  const dateError = isStartDateMissing || isEndDateMissing
    ? "開始日と終了日は必須です。"
    : isDateRangeInvalid
      ? "開始日は終了日以前の日付を指定してください。"
      : undefined
  const isValid = !dateError && selectedTaskIds.length > 0

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!isValid) return
    onSubmit({ startDate, endDate, expectedAssigneeCount, taskIds: selectedTaskIds })
  }

  const toggleTask = (taskId: string) => {
    setSelectedTaskIds((current) => current.includes(taskId)
      ? current.filter((id) => id !== taskId)
      : [...current, taskId])
  }

  return (
    <AppDialog
      open={open}
      onOpenChange={(nextOpen) => { if (!nextOpen) handleClose() }}
      title="Backlogチケット発行"
      size="lg"
      footer={
        <>
          <Button type="button" variant="outline" onClick={handleClose}>キャンセル</Button>
          <Button type="submit" form="backlog-ticket-form" disabled={!isValid}>
            Backlogに{selectedTaskIds.length}件発行
          </Button>
        </>
      }
    >
      <form id="backlog-ticket-form" className="grid gap-5" noValidate onSubmit={handleSubmit}>
        <section className="grid gap-4" aria-labelledby="backlog-ticket-settings-title">
          <div className="flex items-center gap-2">
            <span className="flex size-6 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground">1</span>
            <div>
              <h2 id="backlog-ticket-settings-title" className="font-semibold">Backlog発行設定</h2>
              <p className="text-sm text-muted-foreground">発行するチケットの設定を行ってください。</p>
            </div>
          </div>
          <fieldset className="grid gap-2">
            <legend className="font-medium">期限</legend>
            <div className="flex items-end gap-3">
              <div className="grid flex-1 gap-2">
                <label htmlFor="backlog-ticket-start-date" className="text-sm">開始日</label>
                <Input id="backlog-ticket-start-date" type="date" required value={startDate} onChange={(event) => setStartDate(event.target.value)} aria-invalid={Boolean(dateError)} aria-describedby={dateError ? "backlog-ticket-date-error" : undefined} />
              </div>
              <span aria-hidden="true" className="pb-2 text-muted-foreground">〜</span>
              <div className="grid flex-1 gap-2">
                <label htmlFor="backlog-ticket-end-date" className="text-sm">終了日</label>
                <Input id="backlog-ticket-end-date" type="date" required value={endDate} onChange={(event) => setEndDate(event.target.value)} aria-invalid={Boolean(dateError)} aria-describedby={dateError ? "backlog-ticket-date-error" : undefined} />
              </div>
            </div>
          </fieldset>
          {dateError && <p id="backlog-ticket-date-error" role="alert" className="text-sm text-destructive">{dateError}</p>}
          <div className="grid gap-2">
            <span id="backlog-ticket-assignee-label" className="font-medium">想定担当者数</span>
            <div className="flex items-center gap-2" aria-labelledby="backlog-ticket-assignee-label">
              <Button type="button" variant="outline" size="icon-sm" aria-label="想定担当者数を減らす" disabled={expectedAssigneeCount === 1} onClick={() => setExpectedAssigneeCount((count) => count - 1)}><MinusIcon /></Button>
              <output aria-live="polite" aria-label={`想定担当者数: ${expectedAssigneeCount}人`} className="min-w-16 text-center font-medium">{expectedAssigneeCount}人</output>
              <Button type="button" variant="outline" size="icon-sm" aria-label="想定担当者数を増やす" onClick={() => setExpectedAssigneeCount((count) => count + 1)}><PlusIcon /></Button>
            </div>
          </div>
        </section>

        <section className="grid min-h-0 gap-3" aria-labelledby="backlog-ticket-tasks-title">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <span className="flex size-6 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground">2</span>
              <div>
                <h2 id="backlog-ticket-tasks-title" className="font-semibold">発行するタスク</h2>
                <p aria-live="polite" className="text-sm text-muted-foreground">{selectedTaskIds.length}件を選択中</p>
              </div>
            </div>
            <div className="flex gap-2">
              <Button type="button" variant="outline" size="sm" onClick={() => setSelectedTaskIds(tasks.map((task) => task.id))}>全選択</Button>
              <Button type="button" variant="outline" size="sm" onClick={() => setSelectedTaskIds([])}>全解除</Button>
            </div>
          </div>
          <div className="max-h-56 overflow-y-auto rounded-lg border" aria-label="発行するタスク一覧">
            {tasks.map((task) => {
              const checked = selectedTaskIds.includes(task.id)
              return <label key={task.id} className="flex cursor-pointer items-center gap-3 border-b px-3 py-2 last:border-b-0 hover:bg-muted/50">
                <input type="checkbox" checked={checked} onChange={() => toggleTask(task.id)} aria-label={task.title} />
                <span>{task.title}</span>
              </label>
            })}
          </div>
        </section>
      </form>
    </AppDialog>
  )
}

export { BacklogTicketDialog }
export type { BacklogTicketDialogProps }
