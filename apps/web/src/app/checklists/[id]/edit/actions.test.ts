import { describe, expect, it, vi } from "vitest";

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
    const redirectError = new Error("redirect");
    redirectMock.mockImplementation(() => {
      throw redirectError;
    });
    const formData = new FormData();
    formData.set("name", "更新後の名前");
    formData.set("description", "更新後の説明");

    await expect(updateChecklist("2", previousState, formData)).rejects.toThrow(redirectError);
    expect(redirectMock).toHaveBeenCalledWith("/checklists/2");
  });
});
