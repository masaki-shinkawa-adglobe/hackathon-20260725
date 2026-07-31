import { afterEach, describe, expect, it, vi } from "vitest"

import { POST } from "./route"

describe("POST /api/checklists/ai-bulk-tasks", () => {
  afterEach(() => {
    delete process.env.INTERNAL_API_URL
    vi.unstubAllGlobals()
  })

  it("multipartを内部APIへ中継し、成功JSONを返す", async () => {
    process.env.INTERNAL_API_URL = "http://api:8000"
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ checklist: { id: 1 }, tasks: [] }), { status: 200 }))
    vi.stubGlobal("fetch", fetchMock)
    const formData = new FormData()
    formData.set("checklist_id", "1")
    formData.set("description", "説明")
    formData.append("file", new Blob(["title"], { type: "text/csv" }), "tasks.csv")

    const response = await POST({ formData: async () => formData } as Request)

    expect(response.status).toBe(200)
    expect(await response.json()).toEqual({ checklist: { id: 1 }, tasks: [] })
    const [url, init] = fetchMock.mock.calls[0] as [URL, RequestInit]
    expect(url.toString()).toBe("http://api:8000/checklists/ai-bulk-tasks")
    expect((init.body as FormData).get("description")).toBe("説明")
    expect((init.body as FormData).get("file")).toMatchObject({ name: "tasks.csv" })
  })

  it("未設定、接続失敗、不正な成功応答を安全なエラーへ変換する", async () => {
    const unset = await POST(new Request("http://localhost", { method: "POST", body: new FormData() }))
    expect(unset.status).toBe(503)
    expect((await unset.json()).code).toBe("proxy_not_configured")

    process.env.INTERNAL_API_URL = "http://api:8000"
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("secret endpoint")))
    const failed = await POST(new Request("http://localhost", { method: "POST", body: new FormData() }))
    expect(failed.status).toBe(502)
    expect((await failed.json())).toEqual({ code: "proxy_connection_failed", detail: expect.not.stringContaining("secret") })

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("not json", { status: 200 })))
    const invalid = await POST(new Request("http://localhost", { method: "POST", body: new FormData() }))
    expect(invalid.status).toBe(502)
    expect((await invalid.json()).code).toBe("proxy_invalid_response")
  })

  it("FastAPIのエラーステータスを保持する", async () => {
    process.env.INTERNAL_API_URL = "http://api:8000"
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "Checklist not found" }), { status: 404 })))
    const response = await POST(new Request("http://localhost", { method: "POST", body: new FormData() }))
    expect(response.status).toBe(404)
    expect(await response.json()).toEqual({ code: "upstream_error", detail: "AIタスクの登録に失敗しました。時間をおいて再試行してください。" })
  })
})
