"use server";

import { redirect } from "next/navigation";

export type ChecklistFormState = {
  errors: {
    name?: string;
  };
  values: {
    name: string;
    description: string;
  };
};

export async function createChecklist(
  _previousState: ChecklistFormState,
  formData: FormData,
): Promise<ChecklistFormState> {
  const name = String(formData.get("name") ?? "");
  const description = String(formData.get("description") ?? "");

  if (!name.trim()) {
    return {
      errors: {
        name: "チェックリスト名を入力してください。",
      },
      values: {
        name,
        description,
      },
    };
  }

  redirect("/");
}
