type HealthResult =
  | { ok: true }
  | {
      ok: false;
      message: string;
    };

export const dynamic = "force-dynamic";

async function getHealth(): Promise<HealthResult> {
  const internalApiUrl = process.env.INTERNAL_API_URL;

  if (!internalApiUrl) {
    return {
      ok: false,
      message: "内部 API の接続先が設定されていません。",
    };
  }

  try {
    const response = await fetch(new URL("/health", internalApiUrl), {
      cache: "no-store",
    });

    if (!response.ok) {
      return {
        ok: false,
        message: `ヘルスチェックが HTTP ${response.status} を返しました。`,
      };
    }

    const body: unknown = await response.json();
    if (
      typeof body !== "object" ||
      body === null ||
      !("status" in body) ||
      body.status !== "ok"
    ) {
      return {
        ok: false,
        message: "ヘルスチェックの応答が正常ではありません。",
      };
    }

    return { ok: true };
  } catch {
    return {
      ok: false,
      message: "内部 API へ接続できないか、応答を読み取れませんでした。",
    };
  }
}

function StatusCard({
  name,
  healthy,
  description,
}: {
  name: string;
  healthy: boolean;
  description: string;
}) {
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex items-center justify-between gap-4">
        <h2 className="text-xl font-semibold text-slate-900">{name}</h2>
        <span
          className={`rounded-full px-3 py-1 text-sm font-medium ${
            healthy
              ? "bg-emerald-100 text-emerald-800"
              : "bg-rose-100 text-rose-800"
          }`}
        >
          {healthy ? "正常" : "異常"}
        </span>
      </div>
      <p className="mt-4 text-sm leading-6 text-slate-600">{description}</p>
    </article>
  );
}

export default async function Home() {
  const health = await getHealth();

  return (
    <main className="mx-auto flex min-h-screen max-w-5xl items-center px-6 py-16">
      <div className="w-full">
        <p className="text-sm font-semibold tracking-widest text-blue-700 uppercase">
          Local development
        </p>
        <h1 className="mt-3 text-4xl font-bold tracking-tight text-slate-950 sm:text-5xl">
          開発環境ステータス
        </h1>
        <p className="mt-4 max-w-2xl leading-7 text-slate-600">
          Next.js の Server Component からバックエンドの疎通状態を確認しています。
        </p>

        {!health.ok && (
          <div
            role="alert"
            className="mt-8 rounded-xl border border-rose-200 bg-rose-50 px-5 py-4 text-sm text-rose-900"
          >
            {health.message}
          </div>
        )}

        <section className="mt-8 grid gap-5 md:grid-cols-2">
          <StatusCard
            name="FastAPI"
            healthy={health.ok}
            description={
              health.ok
                ? "GET /health が正常に応答しています。"
                : "API の正常な応答を確認できません。"
            }
          />
          <StatusCard
            name="PostgreSQL"
            healthy={health.ok}
            description={
              health.ok
                ? "FastAPI のヘルスチェックを通じて接続を確認しました。"
                : "データベース接続の正常性を確認できません。"
            }
          />
        </section>
      </div>
    </main>
  );
}
