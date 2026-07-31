import { ChecklistForm } from "./checklist-form";

export default function NewChecklistPage() {
  return (
    <main className="min-h-screen bg-slate-50 px-4 py-10 sm:px-6 sm:py-16">
      <div className="mx-auto max-w-2xl">
        <p className="text-sm font-semibold tracking-wide text-blue-700">CHECKLISTS</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950 sm:text-4xl">
          チェックリストを新規作成
        </h1>
        <p className="mt-3 text-sm leading-6 text-slate-600 sm:text-base">
          基本情報を入力して、新しいチェックリストを作成します。
        </p>

        <section className="mt-8 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-8">
          <h2 className="text-lg font-semibold text-slate-900">基本情報</h2>
          <p className="mt-1 text-sm text-slate-600">チェックリストの名前は必須です。</p>
          <div className="mt-6">
            <ChecklistForm />
          </div>
        </section>
      </div>
    </main>
  );
}
