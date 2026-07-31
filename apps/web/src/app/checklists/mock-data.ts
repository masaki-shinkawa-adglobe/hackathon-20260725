export type Checklist = {
  id: string;
  name: string;
  description: string;
};

export const checklists: Checklist[] = [
  {
    id: "1",
    name: "出張の準備",
    description: "出張前に必要な手配と持ち物を確認します。",
  },
  {
    id: "2",
    name: "イベントの準備",
    description: "イベント開催までに必要な準備を整理します。",
  },
];

export function getChecklistById(id: string): Checklist | undefined {
  return checklists.find((checklist) => checklist.id === id);
}
