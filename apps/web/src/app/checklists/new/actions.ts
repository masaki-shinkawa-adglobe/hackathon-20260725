"use server";

import { redirect } from "next/navigation";

export type ChecklistFormState = {
  errors: {
    name?: string;
  };
  values: {
    name: string;
    description: string;
    backlogProjectKeyOrUrl: string;
  };
};

export async function createChecklist(
  _previousState: ChecklistFormState,
  formData: FormData,
): Promise<ChecklistFormState> {
  const name = String(formData.get("name") ?? "");
  const description = String(formData.get("description") ?? "");
  const backlogProjectKeyOrUrl = String(formData.get("backlog_project_key_or_url") ?? "");
  const trimmedName = name.trim();

  if (!trimmedName) {
    return {
      errors: {
        name: "チェックリスト名を入力してください。",
      },
      values: {
        name,
        description,
        backlogProjectKeyOrUrl,
      },
    };
  }

  if (trimmedName.length > 255) {
    return {
      errors: {
        name: "チェックリスト名は255文字以内で入力してください。",
      },
      values: {
        name,
        description,
        backlogProjectKeyOrUrl,
      },
    };
  }

  const internalApiUrl = process.env.INTERNAL_API_URL;
  if (!internalApiUrl) {
    throw new Error("INTERNAL_API_URL is not configured");
  }

  const response = await fetch(new URL("/checklists", internalApiUrl), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: trimmedName,
      description: description.trim() || null,
      backlog_project_key_or_url: backlogProjectKeyOrUrl.trim() === "" ? null : backlogProjectKeyOrUrl,
    }),
  });

  if (!response.ok) {
    return { errors: {}, values: { name, description, backlogProjectKeyOrUrl } };
  }

  const checklist: { id: number } = await response.json();
  redirect(`/checklists/${checklist.id}`);
}
