import { ChecklistDetail } from "./checklist-detail"

type ChecklistDetailPageProps = {
  params: Promise<{ id: string }>
}

export default async function ChecklistDetailPage({ params }: ChecklistDetailPageProps) {
  const { id } = await params

  return <ChecklistDetail checklistId={id} />
}
