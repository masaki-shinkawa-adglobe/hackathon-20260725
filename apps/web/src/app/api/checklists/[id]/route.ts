import { NextResponse } from "next/server"

const getError = "チェックリストの取得に失敗しました。時間をおいて再試行してください。"
const deleteError = "チェックリストの削除に失敗しました。時間をおいて再試行してください。"
const proxyErrorCodes = {
  notConfigured: "proxy_not_configured",
  connectionFailed: "proxy_connection_failed",
  invalidResponse: "proxy_invalid_response",
  upstream: "upstream_error",
} as const

type RouteContext = {
  params: Promise<{ id: string }>
}

function isChecklistDetail(body: unknown): boolean {
  if (!body || typeof body !== "object") return false

  const checklist = body as { id?: unknown; name?: unknown; description?: unknown; tasks?: unknown }
  return (
    typeof checklist.id === "number" &&
    typeof checklist.name === "string" &&
    (typeof checklist.description === "string" || checklist.description === null) &&
    Array.isArray(checklist.tasks) &&
    checklist.tasks.every((task) => {
      if (!task || typeof task !== "object") return false
      const value = task as { id?: unknown; checklist_id?: unknown; title?: unknown; summary?: unknown; estimated_hours?: unknown }
      return (
        typeof value.id === "number" &&
        typeof value.checklist_id === "number" &&
        typeof value.title === "string" &&
        typeof value.summary === "string" &&
        typeof value.estimated_hours === "number" &&
        Number.isFinite(value.estimated_hours)
      )
    })
  )
}

export async function GET(_request: Request, { params }: RouteContext) {
  const internalApiUrl = process.env.INTERNAL_API_URL
  if (!internalApiUrl) {
    return NextResponse.json({ code: proxyErrorCodes.notConfigured, detail: getError }, { status: 503 })
  }

  const { id } = await params
  let upstreamResponse: Response
  try {
    upstreamResponse = await fetch(new URL(`/checklists/${encodeURIComponent(id)}`, internalApiUrl))
  } catch {
    return NextResponse.json({ code: proxyErrorCodes.connectionFailed, detail: getError }, { status: 502 })
  }

  if (!upstreamResponse.ok) {
    return NextResponse.json({ code: proxyErrorCodes.upstream, detail: getError }, { status: upstreamResponse.status })
  }

  let body: unknown
  try {
    body = await upstreamResponse.json()
  } catch {
    return NextResponse.json({ code: proxyErrorCodes.invalidResponse, detail: getError }, { status: 502 })
  }

  if (!isChecklistDetail(body)) {
    return NextResponse.json({ code: proxyErrorCodes.invalidResponse, detail: getError }, { status: 502 })
  }

  return NextResponse.json(body)
}

export async function DELETE(_request: Request, { params }: RouteContext) {
  const internalApiUrl = process.env.INTERNAL_API_URL
  if (!internalApiUrl) {
    return NextResponse.json({ code: proxyErrorCodes.notConfigured, detail: deleteError }, { status: 503 })
  }

  const { id } = await params
  let upstreamResponse: Response
  try {
    upstreamResponse = await fetch(new URL(`/checklists/${encodeURIComponent(id)}`, internalApiUrl), {
      method: "DELETE",
    })
  } catch {
    return NextResponse.json({ code: proxyErrorCodes.connectionFailed, detail: deleteError }, { status: 502 })
  }

  if (upstreamResponse.status === 204) {
    return new NextResponse(null, { status: 204 })
  }

  return NextResponse.json(
    { code: proxyErrorCodes.upstream, detail: deleteError },
    { status: upstreamResponse.status }
  )
}
