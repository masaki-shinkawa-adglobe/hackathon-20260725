export type ChecklistTask = {
  id: string
  title: string
  summary: string
  estimatedHours: number
}

export type Checklist = {
  id: string
  name: string
  description: string
  tasks: ChecklistTask[]
}

export const checklistMocks: Checklist[] = [
  {
    id: "travel-preparation",
    name: "出張準備チェックリスト",
    description: "出張前に必要な準備を確認するためのチェックリストです。",
    tasks: [
      {
        id: "reserve-transportation",
        title: "移動手段を予約する",
        summary: "新幹線または航空券を予約し、予約内容を共有します。",
        estimatedHours: 1,
      },
      {
        id: "prepare-documents",
        title: "必要書類を準備する",
        summary: "訪問先で必要な資料と身分証を確認します。",
        estimatedHours: 2,
      },
    ],
  },
  {
    id: "new-member-onboarding",
    name: "入社準備チェックリスト",
    description: "新しいメンバーを迎えるための準備を整理します。",
    tasks: [],
  },
]

export function findChecklistById(id: string): Checklist | undefined {
  return checklistMocks.find((checklist) => checklist.id === id)
}
