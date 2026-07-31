import { afterEach, describe, expect, it, vi } from "vitest"

import { POST } from "./route"

const context = (id: string) => ({ params: Promise.resolve({ id }) })

describe("POST /api/checklists/[id]/tasks", () => {
  afterEach(() => {
    delete process.env.INTERNAL_API_URL
    vi.unstubAllGlobals()
  })

  it("内部APIへJSONを中継し、作成済みタスクを201で返す", async () => {
    process.env.INTERNAL_API_URL = "http://api:8000"
    const task = { id: 3, checklist_id: 12, title: "仕訳を確認", summary: null, estimated_hours: 1.5 }
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(task), { status: 201 }))
    vi.stubGlobal("fetch", fetchMock)

    const response = await POST(new Request("http://localhost/api/checklists/12/tasks", {
      method: "POST",
      body: JSON.stringify({ title: "仕訳を確認", summary: null, estimated_hours: 1.5 }),
    }), context("12"))

    expect(response.status).toBe(201)
    expect(await response.json()).toEqual(task)
    expect(fetchMock).toHaveBeenCalledWith(new URL("http://api:8000/checklists/12/tasks"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: "仕訳を確認", summary: null, estimated_hours: 1.5 }),
    })
  })

  it("未設定、接続失敗、不正な送受信内容を安全なエラーへ変換する", async () => {
    const unset = await POST(new Request("http://localhost", { method: "POST", body: "{}" }), context("1"))
    expect(unset.status).toBe(503)
    expect((await unset.json()).code).toBe("proxy_not_configured")

    process.env.INTERNAL_API_URL = "http://api:8000"
    const unreadable = await POST(new Request("http://localhost", { method: "POST", body: "not json" }), context("1"))
    expect(unreadable.status).toBe(422)
    expect((await unreadable.json()).code).toBe("proxy_invalid_response")

    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("secret endpoint")))
    const failed = await POST(new Request("http://localhost", { method: "POST", body: "{}" }), context("1"))
    expect(failed.status).toBe(502)
    expect(await failed.json()).toEqual({ code: "proxy_connection_failed", detail: expect.not.stringContaining("secret") })

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("not json", { status: 201 })))
    const invalidJson = await POST(new Request("http://localhost", { method: "POST", body: "{}" }), context("1"))
    expect(invalidJson.status).toBe(502)
    expect((await invalidJson.json()).code).toBe("proxy_invalid_response")

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: 1 }), { status: 200 })))
    const invalidStatus = await POST(new Request("http://localhost", { method: "POST", body: "{}" }), context("1"))
    expect(invalidStatus.status).toBe(502)
    expect((await invalidStatus.json()).code).toBe("proxy_invalid_response")
  })

  it("FastAPIのエラーステータスを保持する", async () => {
    process.env.INTERNAL_API_URL = "http://api:8000"
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "Checklist not found" }), { status: 404 })))

    const response = await POST(new Request("http://localhost", { method: "POST", body: "{}" }), context("999"))

    expect(response.status).toBe(404)
    expect(await response.json()).toEqual({ code: "upstream_error", detail: "タスクの登録に失敗しました。時間をおいて再試行してください。" })
  })
})
