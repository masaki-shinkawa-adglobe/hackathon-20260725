import { getChecklists } from "./checklists";

export const dynamic = "force-dynamic";

function formatUpdatedAt(value: string): string {
  return new Intl.DateTimeFormat("ja-JP", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export default async function Home() {
  const result = await getChecklists();

  return (
    <main className="mx-auto min-h-screen max-w-5xl px-6 py-16">
      <header>
        <h1 className="text-3xl font-bold text-slate-950">チェックリスト</h1>
        <p className="mt-3 text-sm leading-6 text-slate-600">
          保存済みのチェックリストと進捗を確認できます。
        </p>
      </header>

      {!result.ok && (
        <div
          role="alert"
          className="mt-8 border border-rose-200 bg-rose-50 px-5 py-4 text-sm text-rose-900"
        >
          {result.message}
        </div>
      )}

      {result.ok && result.checklists.length === 0 && (
        <section className="mt-8 border border-dashed border-slate-300 bg-white px-6 py-12 text-center">
          <h2 className="text-lg font-semibold text-slate-900">
            チェックリストはまだありません
          </h2>
          <p className="mt-2 text-sm text-slate-600">
            チェックリストが保存されると、ここに表示されます。
          </p>
        </section>
      )}

      {result.ok && result.checklists.length > 0 && (
        <section className="mt-8 overflow-hidden border border-slate-200 bg-white">
          <ul className="divide-y divide-slate-200">
            {result.checklists.map((checklist) => (
              <li key={`${checklist.name}-${checklist.updatedAt}`} className="px-6 py-5">
                <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
                  <div>
                    <h2 className="text-lg font-semibold text-slate-900">
                      {checklist.name}
                    </h2>
                    <p className="mt-1 text-sm leading-6 text-slate-600">
                      {checklist.description || "説明はありません。"}
                    </p>
                  </div>
                  <dl className="shrink-0 text-sm text-slate-600 sm:text-right">
                    <div>
                      <dt className="sr-only">進捗</dt>
                      <dd className="font-medium text-slate-900">
                        {checklist.completedItemCount} / {checklist.totalItemCount} 完了
                      </dd>
                    </div>
                    <div className="mt-1">
                      <dt className="sr-only">更新日時</dt>
                      <dd>{formatUpdatedAt(checklist.updatedAt)}</dd>
                    </div>
                  </dl>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}
