import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

const notFoundMock = vi.hoisted(() => vi.fn());
const checklistFormMock = vi.hoisted(() => vi.fn(() => <div data-testid="checklist-form" />));

vi.mock("next/navigation", () => ({
  notFound: notFoundMock,
}));

vi.mock("./checklist-form", () => ({
  ChecklistForm: checklistFormMock,
}));

import EditChecklistPage from "./page";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.unstubAllEnvs();
});

test("APIから取得した対象チェックリストの初期値をフォームへ渡す", async () => {
  vi.stubEnv("INTERNAL_API_URL", "http://api:8000");
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ id: 1, name: "出張の準備", description: "出張前に必要な手配と持ち物を確認します。" }),
      ),
    ),
  );

  render(await EditChecklistPage({ params: Promise.resolve({ id: "1" }) }));

  expect(screen.getByRole("heading", { name: "チェックリストを編集", level: 1 })).toBeInTheDocument();
  expect(checklistFormMock).toHaveBeenCalledWith(
    {
      checklistId: "1",
      initialValues: {
        name: "出張の準備",
        description: "出張前に必要な手配と持ち物を確認します。",
      },
    },
    undefined,
  );
  expect(fetch).toHaveBeenCalledWith(new URL("http://api:8000/checklists/1"));
});

test("APIが404を返す場合はnotFoundを呼び出す", async () => {
  vi.stubEnv("INTERNAL_API_URL", "http://api:8000");
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 404 })));
  const notFoundError = new Error("not found");
  notFoundMock.mockImplementation(() => {
    throw notFoundError;
  });

  await expect(EditChecklistPage({ params: Promise.resolve({ id: "unknown" }) })).rejects.toThrow(
    notFoundError,
  );
  expect(notFoundMock).toHaveBeenCalledOnce();
});
