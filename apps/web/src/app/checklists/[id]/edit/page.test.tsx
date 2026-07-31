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
});

test("対象チェックリストの初期値をフォームへ渡す", async () => {
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
});

test("存在しないIDではnotFoundを呼び出す", async () => {
  const notFoundError = new Error("not found");
  notFoundMock.mockImplementation(() => {
    throw notFoundError;
  });

  await expect(EditChecklistPage({ params: Promise.resolve({ id: "unknown" }) })).rejects.toThrow(
    notFoundError,
  );
  expect(notFoundMock).toHaveBeenCalledOnce();
});
