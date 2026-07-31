import { cleanup, render, screen } from "@testing-library/react";
import type { ComponentProps } from "react";
import { afterEach, expect, test, vi } from "vitest";

vi.mock("next/link", () => ({
  default: ({ children, ...props }: ComponentProps<"a">) => <a {...props}>{children}</a>,
}));

import { ChecklistForm } from "./checklist-form";

afterEach(cleanup);

test("初期値、保存操作、キャンセル先を表示する", () => {
  render(
    <ChecklistForm
      checklistId="1"
      initialValues={{
        name: "出張の準備",
        description: "出張前に必要な手配と持ち物を確認します。",
      }}
    />,
  );

  expect(screen.getByLabelText(/チェックリスト名/)).toHaveValue("出張の準備");
  expect(screen.getByLabelText(/説明/)).toHaveValue(
    "出張前に必要な手配と持ち物を確認します。",
  );
  expect(screen.getByRole("button", { name: "保存する" })).toBeEnabled();
  expect(screen.getByRole("link", { name: "キャンセル" })).toHaveAttribute(
    "href",
    "/checklists/1",
  );
});
