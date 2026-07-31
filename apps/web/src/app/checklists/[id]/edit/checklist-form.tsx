"use client";

import Link from "next/link";
import { useActionState } from "react";
import { useFormStatus } from "react-dom";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

import { updateChecklist } from "./actions";
import type { ChecklistFormState } from "./actions";

type ChecklistFormProps = {
  checklistId: string;
  initialValues: ChecklistFormState["values"];
};

function SubmitButton() {
  const { pending } = useFormStatus();

  return (
    <Button
      type="submit"
      disabled={pending}
      aria-disabled={pending}
      className="min-h-11 px-5 py-2.5"
    >
      {pending ? "保存中..." : "保存する"}
    </Button>
  );
}

export function ChecklistForm({ checklistId, initialValues }: ChecklistFormProps) {
  const [state, formAction] = useActionState(updateChecklist.bind(null, checklistId), {
    errors: {},
    values: initialValues,
  });

  return (
    <form action={formAction} className="space-y-6" noValidate>
      <div>
        <label htmlFor="name" className="block text-sm font-semibold text-foreground">
          チェックリスト名{" "}
          <span className="ml-1 rounded bg-destructive/10 px-1.5 py-0.5 text-xs font-medium text-destructive">
            必須
          </span>
        </label>
        <Input
          id="name"
          name="name"
          type="text"
          defaultValue={state.values.name}
          aria-describedby={state.errors.name ? "name-error" : undefined}
          aria-invalid={Boolean(state.errors.name)}
          className="mt-2"
          placeholder="例: 出張の準備"
        />
        {state.errors.name && (
          <p id="name-error" className="mt-2 text-sm text-destructive" role="alert">
            {state.errors.name}
          </p>
        )}
      </div>

      <div>
        <label htmlFor="backlog_project_key_or_url" className="block text-sm font-semibold text-foreground">
          BacklogプロジェクトキーまたはURL <span className="text-muted-foreground">（任意）</span>
        </label>
        <Input
          id="backlog_project_key_or_url"
          name="backlog_project_key_or_url"
          type="text"
          defaultValue={state.values.backlogProjectKeyOrUrl}
          className="mt-2"
          placeholder="例: PROJ または https://example.backlog.com/projects/PROJ"
        />
      </div>

      <div>
        <label htmlFor="description" className="block text-sm font-semibold text-foreground">
          説明 <span className="text-muted-foreground">（任意）</span>
        </label>
        <textarea
          id="description"
          name="description"
          rows={5}
          defaultValue={state.values.description}
          className="mt-2 block w-full resize-y rounded-lg border border-input bg-background px-3 py-2.5 text-foreground outline-none transition placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
          placeholder="このチェックリストの用途を入力してください。"
        />
      </div>

      <div className="flex flex-col-reverse gap-3 border-t border-border pt-6 sm:flex-row sm:justify-end">
        <Button asChild variant="outline" className="min-h-11 px-5 py-2.5">
          <Link href={`/checklists/${checklistId}`}>キャンセル</Link>
        </Button>
        <SubmitButton />
      </div>
    </form>
  );
}
