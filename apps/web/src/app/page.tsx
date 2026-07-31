import { ChecklistList, type ChecklistListItem } from "./checklist-list"

type ChecklistsResponse = {
  checklists: ChecklistListItem[]
}

export default async function Home() {
  const internalApiUrl = process.env.INTERNAL_API_URL
  if (!internalApiUrl) {
    throw new Error("INTERNAL_API_URL is not configured")
  }

  const response = await fetch(new URL("/checklists", internalApiUrl))
  if (!response.ok) {
    throw new Error("Failed to fetch checklists")
  }

  const { checklists }: ChecklistsResponse = await response.json()

  return <ChecklistList checklists={checklists} />
}
