import { afterEach, describe, expect, it, vi } from "vitest"

import { GET } from "./route"

const context = (id: string) => ({ params: Promise.resolve({ id }) })

describe("GET /api/checklists/[id]", () => {
  afterEach(() => {
    delete process.env.INTERNAL_API_URL
    vi.unstubAllGlobals()
  })

  it("内部APIへ正しいGETを中継し、成功JSONを返す", async () => {
    process.env.INTERNAL_API_URL = "http://api:8000"
    const detail = { id: 12, name: "月次決算", description: "月ごとの締め作業", tasks: [] }
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(detail), { status: 200 }))
    vi.stubGlobal("fetch", fetchMock)

    const response = await GET(new Request("http://localhost/api/checklists/12"), context("12"))

    expect(response.status).toBe(200)
    expect(await response.json()).toEqual(detail)
    expect(fetchMock).toHaveBeenCalledWith(new URL("http://api:8000/checklists/12"))
  })

  it("未設定、接続失敗、不正応答を安全なエラーへ変換する", async () => {
    const unset = await GET(new Request("http://localhost"), context("1"))
    expect(unset.status).toBe(503)
    expect((await unset.json()).code).toBe("proxy_not_configured")

    process.env.INTERNAL_API_URL = "http://api:8000"
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("secret endpoint")))
    const failed = await GET(new Request("http://localhost"), context("1"))
    expect(failed.status).toBe(502)
    expect(await failed.json()).toEqual({ code: "proxy_connection_failed", detail: expect.not.stringContaining("secret") })

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("not json", { status: 200 })))
    const invalidJson = await GET(new Request("http://localhost"), context("1"))
    expect(invalidJson.status).toBe(502)
    expect((await invalidJson.json()).code).toBe("proxy_invalid_response")

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: 1, name: "名前", description: null, tasks: [{}] }), { status: 200 })))
    const invalidShape = await GET(new Request("http://localhost"), context("1"))
    expect(invalidShape.status).toBe(502)
    expect((await invalidShape.json()).code).toBe("proxy_invalid_response")
  })

  it("FastAPIのエラーステータスを保持する", async () => {
    process.env.INTERNAL_API_URL = "http://api:8000"
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "Checklist not found" }), { status: 404 })))

    const response = await GET(new Request("http://localhost"), context("999"))

    expect(response.status).toBe(404)
    expect(await response.json()).toEqual({ code: "upstream_error", detail: "チェックリストの取得に失敗しました。時間をおいて再試行してください。" })
  })
})
