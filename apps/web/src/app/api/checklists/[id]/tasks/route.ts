import { NextResponse } from "next/server"

const genericError = "タスクの登録に失敗しました。時間をおいて再試行してください。"
const proxyErrorCodes = {
  notConfigured: "proxy_not_configured",
  connectionFailed: "proxy_connection_failed",
  invalidResponse: "proxy_invalid_response",
  upstream: "upstream_error",
} as const

type RouteContext = {
  params: Promise<{ id: string }>
}

function isTask(body: unknown): boolean {
  if (!body || typeof body !== "object") return false

  const task = body as { id?: unknown; checklist_id?: unknown; title?: unknown; summary?: unknown; estimated_hours?: unknown }
  return (
    typeof task.id === "number" &&
    typeof task.checklist_id === "number" &&
    typeof task.title === "string" &&
    (typeof task.summary === "string" || task.summary === null) &&
    typeof task.estimated_hours === "number" &&
    Number.isFinite(task.estimated_hours)
  )
}

export async function POST(request: Request, { params }: RouteContext) {
  const internalApiUrl = process.env.INTERNAL_API_URL
  if (!internalApiUrl) {
    return NextResponse.json({ code: proxyErrorCodes.notConfigured, detail: genericError }, { status: 503 })
  }

  let body: unknown
  try {
    body = await request.json()
  } catch {
    return NextResponse.json({ code: proxyErrorCodes.invalidResponse, detail: "送信内容を読み取れませんでした。" }, { status: 422 })
  }
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    return NextResponse.json({ code: proxyErrorCodes.invalidResponse, detail: "送信内容を読み取れませんでした。" }, { status: 422 })
  }

  const taskInput = body as { title?: unknown; summary?: unknown; estimated_hours?: unknown }
  const upstreamBody = {
    title: taskInput.title,
    summary: taskInput.summary,
    estimated_hours: taskInput.estimated_hours,
  }

  const { id } = await params
  let upstreamResponse: Response
  try {
    upstreamResponse = await fetch(new URL(`/checklists/${encodeURIComponent(id)}/tasks`, internalApiUrl), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(upstreamBody),
    })
  } catch {
    return NextResponse.json({ code: proxyErrorCodes.connectionFailed, detail: genericError }, { status: 502 })
  }

  if (!upstreamResponse.ok) {
    return NextResponse.json({ code: proxyErrorCodes.upstream, detail: genericError }, { status: upstreamResponse.status })
  }

  let createdTask: unknown
  try {
    createdTask = await upstreamResponse.json()
  } catch {
    return NextResponse.json({ code: proxyErrorCodes.invalidResponse, detail: genericError }, { status: 502 })
  }

  if (upstreamResponse.status !== 201 || !isTask(createdTask)) {
    return NextResponse.json({ code: proxyErrorCodes.invalidResponse, detail: genericError }, { status: 502 })
  }

  return NextResponse.json(createdTask, { status: 201 })
}
