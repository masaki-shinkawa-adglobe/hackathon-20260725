export type Checklist = {
  name: string;
  description: string | null;
  completedItemCount: number;
  totalItemCount: number;
  updatedAt: string;
};

export type ChecklistResult =
  | { ok: true; checklists: Checklist[] }
  | { ok: false; message: string };

type ChecklistApiResponse = {
  name: string;
  description: string | null;
  completed_item_count: number;
  total_item_count: number;
  updated_at: string;
};

function isChecklistApiResponse(value: unknown): value is ChecklistApiResponse {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const item = value as Record<string, unknown>;
  return (
    typeof item.name === "string" &&
    (typeof item.description === "string" || item.description === null) &&
    typeof item.completed_item_count === "number" &&
    Number.isInteger(item.completed_item_count) &&
    typeof item.total_item_count === "number" &&
    Number.isInteger(item.total_item_count) &&
    typeof item.updated_at === "string" &&
    !Number.isNaN(Date.parse(item.updated_at))
  );
}

export async function getChecklists(): Promise<ChecklistResult> {
  const internalApiUrl = process.env.INTERNAL_API_URL;
  if (!internalApiUrl) {
    return { ok: false, message: "内部 API の接続先が設定されていません。" };
  }

  try {
    const response = await fetch(new URL("/checklists", internalApiUrl), {
      cache: "no-store",
    });
    if (!response.ok) {
      return {
        ok: false,
        message: `チェックリストの取得に失敗しました (HTTP ${response.status})。`,
      };
    }

    let body: unknown;
    try {
      body = await response.json();
    } catch {
      return {
        ok: false,
        message: "チェックリストの応答を読み取れませんでした。",
      };
    }
    if (!Array.isArray(body) || !body.every(isChecklistApiResponse)) {
      return {
        ok: false,
        message: "チェックリストの応答形式が正しくありません。",
      };
    }

    return {
      ok: true,
      checklists: body.map((item) => ({
        name: item.name,
        description: item.description,
        completedItemCount: item.completed_item_count,
        totalItemCount: item.total_item_count,
        updatedAt: item.updated_at,
      })),
    };
  } catch {
    return {
      ok: false,
      message: "内部 API へ接続できないか、応答を読み取れませんでした。",
    };
  }
}
