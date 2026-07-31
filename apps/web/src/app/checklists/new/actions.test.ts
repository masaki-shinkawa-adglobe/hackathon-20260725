import { afterEach, describe, expect, it, vi } from "vitest"

const redirectMock = vi.hoisted(() => vi.fn())

vi.mock("next/navigation", () => ({ redirect: redirectMock }))

import { createChecklist, type ChecklistFormState } from "./actions"

const previousState: ChecklistFormState = {
  errors: {},
  values: { name: "以前の名前", description: "以前の説明" },
}

describe("createChecklist", () => {
  afterEach(() => {
    vi.clearAllMocks()
    vi.unstubAllEnvs()
  })

  it("空白のみと256文字の名前を検証し、入力値を保持する", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const empty = new FormData()
    empty.set("name", "   ")
    empty.set("description", "説明")
    await expect(createChecklist(previousState, empty)).resolves.toEqual({
      errors: { name: "チェックリスト名を入力してください。" },
      values: { name: "   ", description: "説明" },
    })

    const tooLong = new FormData()
    tooLong.set("name", "a".repeat(256))
    tooLong.set("description", "説明")
    await expect(createChecklist(previousState, tooLong)).resolves.toEqual({
      errors: { name: "チェックリスト名は255文字以内で入力してください。" },
      values: { name: "a".repeat(256), description: "説明" },
    })
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it("有効な入力をAPIへ送信し、作成した詳細画面へ遷移する", async () => {
    vi.stubEnv("INTERNAL_API_URL", "http://api:8000")
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: 3 }), { status: 201 })))
    const redirectError = new Error("redirect")
    redirectMock.mockImplementation(() => { throw redirectError })
    const formData = new FormData()
    formData.set("name", " 新しいチェックリスト ")
    formData.set("description", "   ")

    await expect(createChecklist(previousState, formData)).rejects.toThrow(redirectError)
    expect(fetch).toHaveBeenCalledWith(new URL("http://api:8000/checklists"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: "新しいチェックリスト", description: null }),
    })
    expect(redirectMock).toHaveBeenCalledWith("/checklists/3")
  })
})
