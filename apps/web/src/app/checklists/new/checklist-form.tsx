"use client";

import Link from "next/link";
import { useActionState } from "react";
import { useFormStatus } from "react-dom";

import {
  createChecklist,
} from "./actions";
import type { ChecklistFormState } from "./actions";

const initialChecklistFormState: ChecklistFormState = {
  errors: {},
  values: {
    name: "",
    description: "",
    backlogProjectKeyOrUrl: "",
  },
};

function SubmitButton() {
  const { pending } = useFormStatus();

  return (
    <button
      type="submit"
      disabled={pending}
      className="inline-flex min-h-11 items-center justify-center rounded-lg bg-blue-700 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-blue-800 disabled:cursor-not-allowed disabled:bg-blue-400"
    >
      {pending ? "作成中..." : "作成する"}
    </button>
  );
}

export function ChecklistForm() {
  const [state, formAction] = useActionState(
    createChecklist,
    initialChecklistFormState,
  );

  return (
    <form action={formAction} className="space-y-6" noValidate>
      <div>
        <label htmlFor="name" className="block text-sm font-semibold text-slate-800">
          チェックリスト名 <span className="ml-1 rounded bg-rose-100 px-1.5 py-0.5 text-xs font-medium text-rose-700">必須</span>
        </label>
        <input
          id="name"
          name="name"
          type="text"
          defaultValue={state.values.name}
          maxLength={255}
          aria-describedby={state.errors.name ? "name-error" : undefined}
          aria-invalid={Boolean(state.errors.name)}
          className="mt-2 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-blue-600 focus:ring-2 focus:ring-blue-100"
          placeholder="例: 出張の準備"
        />
        {state.errors.name && (
          <p id="name-error" className="mt-2 text-sm text-rose-700">
            {state.errors.name}
          </p>
        )}
      </div>

      <div>
        <label htmlFor="backlog_project_key_or_url" className="block text-sm font-semibold text-slate-800">
          BacklogプロジェクトキーまたはURL <span className="text-slate-500">（任意）</span>
        </label>
        <input
          id="backlog_project_key_or_url"
          name="backlog_project_key_or_url"
          type="text"
          defaultValue={state.values.backlogProjectKeyOrUrl}
          className="mt-2 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-blue-600 focus:ring-2 focus:ring-blue-100"
          placeholder="例: PROJ または https://example.backlog.com/projects/PROJ"
        />
      </div>

      <div>
        <label htmlFor="description" className="block text-sm font-semibold text-slate-800">
          説明 <span className="text-slate-500">（任意）</span>
        </label>
        <textarea
          id="description"
          name="description"
          rows={5}
          defaultValue={state.values.description}
          className="mt-2 block w-full resize-y rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-blue-600 focus:ring-2 focus:ring-blue-100"
          placeholder="このチェックリストの用途を入力してください。"
        />
      </div>

      <div className="flex flex-col-reverse gap-3 border-t border-slate-200 pt-6 sm:flex-row sm:justify-end">
        <Link
          href="/"
          className="inline-flex min-h-11 items-center justify-center rounded-lg border border-slate-300 bg-white px-5 py-2.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
        >
          キャンセル
        </Link>
        <SubmitButton />
      </div>
    </form>
  );
}
