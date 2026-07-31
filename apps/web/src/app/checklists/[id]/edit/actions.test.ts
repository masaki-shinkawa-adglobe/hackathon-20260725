import { afterEach, describe, expect, it, vi } from "vitest";

const redirectMock = vi.hoisted(() => vi.fn());

vi.mock("next/navigation", () => ({
  redirect: redirectMock,
}));

import { updateChecklist, type ChecklistFormState } from "./actions";

const previousState: ChecklistFormState = {
  errors: {},
  values: {
    name: "以前の名前",
    description: "以前の説明",
  },
};

describe("updateChecklist", () => {
  afterEach(() => {
    vi.clearAllMocks();
    vi.unstubAllEnvs();
  });

  it("空白のみの名称をエラーにし、入力値を保持する", async () => {
    const formData = new FormData();
    formData.set("name", "   ");
    formData.set("description", "入力した説明");

    await expect(updateChecklist("1", previousState, formData)).resolves.toEqual({
      errors: {
        name: "チェックリスト名を入力してください。",
      },
      values: {
        name: "   ",
        description: "入力した説明",
      },
    });
    expect(redirectMock).not.toHaveBeenCalled();
  });

  it("有効な入力では対象チェックリストの詳細画面へ遷移する", async () => {
    vi.stubEnv("INTERNAL_API_URL", "http://api:8000");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 200 })));
    const redirectError = new Error("redirect");
    redirectMock.mockImplementation(() => {
      throw redirectError;
    });
    const formData = new FormData();
    formData.set("name", " 更新後の名前 ");
    formData.set("description", "   ");

    await expect(updateChecklist("2", previousState, formData)).rejects.toThrow(redirectError);
    expect(fetch).toHaveBeenCalledWith(new URL("http://api:8000/checklists/2"), {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: "更新後の名前", description: null }),
    });
    expect(redirectMock).toHaveBeenCalledWith("/checklists/2");
  });

  it("256文字の名称をエラーにし、APIを呼び出さない", async () => {
    const formData = new FormData();
    formData.set("name", "a".repeat(256));
    formData.set("description", "入力した説明");

    await expect(updateChecklist("1", previousState, formData)).resolves.toEqual({
      errors: { name: "チェックリスト名は255文字以内で入力してください。" },
      values: { name: "a".repeat(256), description: "入力した説明" },
    });
    expect(fetch).not.toHaveBeenCalled();
  });
});
