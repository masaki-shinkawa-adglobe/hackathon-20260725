export type ChecklistTask = {
  id: string
  title: string
  summary: string
  estimatedHours: number
  priority?: "low" | "medium" | "high"
}

export type Checklist = {
  id: string
  name: string
  description: string
  tasks: ChecklistTask[]
}

export const checklists: Checklist[] = [
  {
    id: "1",
    name: "出張の準備",
    description: "出張前に必要な準備を確認するチェックリストです。",
    tasks: [
      {
        id: "travel-arrangements",
        title: "交通機関と宿泊先を手配する",
        summary: "移動時間と宿泊先を確定し、予約内容を共有します。",
        estimatedHours: 1,
        priority: "high",
      },
      {
        id: "packing",
        title: "持ち物を準備する",
        summary: "業務に必要な機器、書類、衣類を用意します。",
        estimatedHours: 0.5,
      },
    ],
  },
  {
    id: "2",
    name: "月次決算",
    description: "月次決算の作業を整理するチェックリストです。",
    tasks: [],
  },
]

export function findChecklistById(id: string) {
  return checklists.find((checklist) => checklist.id === id)
}

export function findTaskByChecklistIdAndTaskId(checklistId: string, taskId: string) {
  const checklist = findChecklistById(checklistId)
  const task = checklist?.tasks.find((candidate) => candidate.id === taskId)

  return checklist && task ? { checklist, task } : undefined
}
