import { notFound } from "next/navigation";

import { getChecklistById } from "../../mock-data";
import { ChecklistForm } from "./checklist-form";

type EditChecklistPageProps = {
  params: Promise<{
    id: string;
  }>;
};

export default async function EditChecklistPage({ params }: EditChecklistPageProps) {
  const { id } = await params;
  const checklist = getChecklistById(id);

  if (!checklist) {
    notFound();
  }

  return (
    <main className="min-h-screen bg-muted/30 px-4 py-10 sm:px-6 sm:py-16">
      <div className="mx-auto max-w-2xl">
        <p className="text-sm font-semibold tracking-wide text-primary">CHECKLISTS</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
          チェックリストを編集
        </h1>
        <p className="mt-3 text-sm leading-6 text-muted-foreground sm:text-base">
          基本情報を編集して、チェックリストを更新します。
        </p>

        <section className="mt-8 rounded-2xl border border-border bg-card p-5 text-card-foreground shadow-sm sm:p-8">
          <h2 className="text-lg font-semibold">基本情報</h2>
          <p className="mt-1 text-sm text-muted-foreground">チェックリストの名前は必須です。</p>
          <div className="mt-6">
            <ChecklistForm
              checklistId={checklist.id}
              initialValues={{
                name: checklist.name,
                description: checklist.description,
              }}
            />
          </div>
        </section>
      </div>
    </main>
  );
}
