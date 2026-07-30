import assert from "node:assert/strict";
import { afterEach, test } from "node:test";

import { getChecklists } from "./checklists.ts";

const originalFetch = globalThis.fetch;
const originalInternalApiUrl = process.env.INTERNAL_API_URL;

afterEach(() => {
  globalThis.fetch = originalFetch;
  if (originalInternalApiUrl === undefined) {
    delete process.env.INTERNAL_API_URL;
  } else {
    process.env.INTERNAL_API_URL = originalInternalApiUrl;
  }
});

test("正常な一覧応答を画面用の形式に変換する", async () => {
  process.env.INTERNAL_API_URL = "http://api:8000";
  globalThis.fetch = async () =>
    new Response(
      JSON.stringify([
        {
          name: "リリース準備",
          description: null,
          completed_item_count: 1,
          total_item_count: 2,
          updated_at: "2026-07-31T12:00:00Z",
        },
      ]),
      { status: 200 },
    );

  assert.deepEqual(await getChecklists(), {
    ok: true,
    checklists: [
      {
        name: "リリース準備",
        description: null,
        completedItemCount: 1,
        totalItemCount: 2,
        updatedAt: "2026-07-31T12:00:00Z",
      },
    ],
  });
});

test("空の一覧応答を受け入れる", async () => {
  process.env.INTERNAL_API_URL = "http://api:8000";
  globalThis.fetch = async () => new Response("[]", { status: 200 });

  assert.deepEqual(await getChecklists(), { ok: true, checklists: [] });
});

test("不正な応答形式をエラーにする", async () => {
  process.env.INTERNAL_API_URL = "http://api:8000";
  globalThis.fetch = async () => new Response("{}", { status: 200 });

  assert.deepEqual(await getChecklists(), {
    ok: false,
    message: "チェックリストの応答形式が正しくありません。",
  });
});

test("JSON解析失敗を利用者向けエラーにする", async () => {
  process.env.INTERNAL_API_URL = "http://api:8000";
  globalThis.fetch = async () => new Response("{", { status: 200 });

  assert.deepEqual(await getChecklists(), {
    ok: false,
    message: "チェックリストの応答を読み取れませんでした。",
  });
});

test("HTTPエラーを利用者向けエラーにする", async () => {
  process.env.INTERNAL_API_URL = "http://api:8000";
  globalThis.fetch = async () => new Response("", { status: 503 });

  assert.deepEqual(await getChecklists(), {
    ok: false,
    message: "チェックリストの取得に失敗しました (HTTP 503)。",
  });
});

test("接続失敗を利用者向けエラーにする", async () => {
  process.env.INTERNAL_API_URL = "http://api:8000";
  globalThis.fetch = async () => {
    throw new Error("connection failed");
  };

  assert.deepEqual(await getChecklists(), {
    ok: false,
    message: "内部 API へ接続できないか、応答を読み取れませんでした。",
  });
});

test("接続先未設定を利用者向けエラーにする", async () => {
  delete process.env.INTERNAL_API_URL;

  assert.deepEqual(await getChecklists(), {
    ok: false,
    message: "内部 API の接続先が設定されていません。",
  });
});
