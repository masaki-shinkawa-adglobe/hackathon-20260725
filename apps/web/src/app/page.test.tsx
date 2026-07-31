import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";

import Home from "./page";

afterEach(() => {
  cleanup();
});

test("チェックリスト一覧の全列見出しとモックデータを表示する", () => {
  render(<Home />);

  expect(screen.getByRole("columnheader", { name: "チェックリスト名" })).toHaveAttribute(
    "scope",
    "col",
  );
  expect(screen.getByRole("columnheader", { name: "説明" })).toHaveAttribute("scope", "col");
  expect(screen.getByRole("columnheader", { name: "完了済み項目数" })).toHaveAttribute(
    "scope",
    "col",
  );
  expect(screen.getByRole("columnheader", { name: "総項目数" })).toHaveAttribute("scope", "col");
  expect(screen.getByRole("columnheader", { name: "更新日時" })).toHaveAttribute(
    "scope",
    "col",
  );

  expect(screen.getByRole("cell", { name: "出張の準備" })).toBeInTheDocument();
  expect(
    screen.getByRole("cell", {
      name: "来週の大阪出張に必要な持ち物と手配を確認します。",
    }),
  ).toBeInTheDocument();
  expect(screen.getByRole("cell", { name: "4" })).toBeInTheDocument();
  expect(screen.getByRole("cell", { name: "6" })).toBeInTheDocument();
  expect(screen.getByRole("cell", { name: "2026年7月30日 14:30" })).toBeInTheDocument();

  expect(screen.getByRole("cell", { name: "新入社員の受け入れ" })).toBeInTheDocument();
  expect(
    screen.getByRole("cell", {
      name: "入社初日に必要なアカウント発行と備品準備の一覧です。",
    }),
  ).toBeInTheDocument();
  expect(screen.getByRole("cell", { name: "7" })).toBeInTheDocument();
  expect(screen.getByRole("cell", { name: "8" })).toBeInTheDocument();
  expect(screen.getByRole("cell", { name: "2026年7月29日 10:15" })).toBeInTheDocument();

  expect(screen.getByRole("cell", { name: "月次締め作業" })).toBeInTheDocument();
  expect(
    screen.getByRole("cell", { name: "経費精算とレポート提出の進捗を管理します。" }),
  ).toBeInTheDocument();
  expect(screen.getByRole("cell", { name: "2" })).toBeInTheDocument();
  expect(screen.getByRole("cell", { name: "5" })).toBeInTheDocument();
  expect(screen.getByRole("cell", { name: "2026年7月28日 17:45" })).toBeInTheDocument();
});
