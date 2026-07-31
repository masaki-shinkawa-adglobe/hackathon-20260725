import { NextResponse } from "next/server"

const genericError = "AIタスクの登録に失敗しました。時間をおいて再試行してください。"
const proxyErrorCodes = {
  notConfigured: "proxy_not_configured",
  connectionFailed: "proxy_connection_failed",
  invalidResponse: "proxy_invalid_response",
  upstream: "upstream_error",
} as const

export async function POST(request: Request) {
  const internalApiUrl = process.env.INTERNAL_API_URL
  if (!internalApiUrl) {
    return NextResponse.json({ code: proxyErrorCodes.notConfigured, detail: genericError }, { status: 503 })
  }

  let formData: FormData
  try {
    formData = await request.formData()
  } catch {
    return NextResponse.json({ code: proxyErrorCodes.invalidResponse, detail: "送信内容を読み取れませんでした。" }, { status: 422 })
  }

  const upstreamFormData = new FormData()
  for (const key of ["checklist_id", "description", "file"] as const) {
    const value = formData.get(key)
    if (value !== null) upstreamFormData.append(key, value)
  }

  let upstreamResponse: Response
  try {
    upstreamResponse = await fetch(new URL("/checklists/ai-bulk-tasks", internalApiUrl), {
      method: "POST",
      body: upstreamFormData,
    })
  } catch {
    return NextResponse.json({ code: proxyErrorCodes.connectionFailed, detail: genericError }, { status: 502 })
  }

  if (!upstreamResponse.ok) {
    return NextResponse.json({ code: proxyErrorCodes.upstream, detail: genericError }, { status: upstreamResponse.status })
  }

  let body: unknown
  try {
    body = await upstreamResponse.json()
  } catch {
    return NextResponse.json({ code: proxyErrorCodes.invalidResponse, detail: genericError }, { status: 502 })
  }

  if (!body || typeof body !== "object" || !Array.isArray((body as { tasks?: unknown }).tasks)) {
    return NextResponse.json({ code: proxyErrorCodes.invalidResponse, detail: genericError }, { status: 502 })
  }
  return NextResponse.json(body)
}
