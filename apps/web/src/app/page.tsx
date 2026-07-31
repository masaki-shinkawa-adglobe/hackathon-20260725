import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const checklists = [
  {
    name: "出張の準備",
    description: "来週の大阪出張に必要な持ち物と手配を確認します。",
    completedItemCount: 4,
    totalItemCount: 6,
    updatedAt: "2026年7月30日 14:30",
  },
  {
    name: "新入社員の受け入れ",
    description: "入社初日に必要なアカウント発行と備品準備の一覧です。",
    completedItemCount: 7,
    totalItemCount: 8,
    updatedAt: "2026年7月29日 10:15",
  },
  {
    name: "月次締め作業",
    description: "経費精算とレポート提出の進捗を管理します。",
    completedItemCount: 2,
    totalItemCount: 5,
    updatedAt: "2026年7月28日 17:45",
  },
];

export default function Home() {
  return (
    <main className="min-h-screen bg-muted/30 px-10 py-14">
      <div className="mx-auto w-full max-w-6xl">
        <p className="text-sm font-semibold tracking-widest text-muted-foreground uppercase">
          Checklists
        </p>
        <h1 className="mt-3 text-4xl font-bold tracking-tight text-foreground">
          チェックリスト一覧
        </h1>
        <p className="mt-4 text-base text-muted-foreground">
          保存したチェックリストの進捗を確認できます。
        </p>

        <section
          className="mt-8 overflow-hidden rounded-xl border bg-card shadow-sm"
          aria-labelledby="checklist-table-heading"
        >
          <h2 id="checklist-table-heading" className="sr-only">
            チェックリスト一覧
          </h2>
          <Table>
            <TableHeader className="bg-muted/50">
              <TableRow>
                <TableHead scope="col">チェックリスト名</TableHead>
                <TableHead scope="col">説明</TableHead>
                <TableHead scope="col" className="text-right">
                  完了済み項目数
                </TableHead>
                <TableHead scope="col" className="text-right">
                  総項目数
                </TableHead>
                <TableHead scope="col">更新日時</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {checklists.map((checklist) => (
                <TableRow key={checklist.name}>
                  <TableCell className="font-medium text-foreground">
                    {checklist.name}
                  </TableCell>
                  <TableCell className="whitespace-normal text-muted-foreground">
                    {checklist.description}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {checklist.completedItemCount}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {checklist.totalItemCount}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {checklist.updatedAt}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </section>
      </div>
    </main>
  );
}
