import {
  CalendarDaysIcon,
  KeyRoundIcon,
  MessageSquareMoreIcon,
  PlugZapIcon,
  Rows3Icon,
  SaveIcon,
  SendIcon,
} from "lucide-react"
import type { ComponentType, ReactNode } from "react"

import { AppBreadcrumb } from "@/components/app-breadcrumb"
import { AppSidebar } from "@/components/app-sidebar"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

type IntegrationCardProps = {
  service: string
  description: string
  icon: ComponentType<{ className?: string; "aria-hidden"?: "true" | "false" }>
  children: ReactNode
}

const connectionHistory = [
  { service: "Backlog", lastChecked: "未接続", status: "未接続" },
  { service: "Slack", lastChecked: "未接続", status: "未接続" },
  { service: "Googleカレンダー", lastChecked: "未接続", status: "未接続" },
]

function IntegrationCard({
  service,
  description,
  icon: Icon,
  children,
}: IntegrationCardProps) {
  return (
    <section className="relative overflow-hidden rounded-xl border border-border bg-card shadow-sm">
      <fieldset
        disabled
        aria-describedby={`${service}-coming-soon`}
        className="space-y-5 p-6"
      >
        <legend className="sr-only">{service}連携設定</legend>
        <div className="flex items-start gap-3">
          <div className="rounded-lg bg-muted p-2.5 text-muted-foreground">
            <Icon aria-hidden="true" className="size-5" />
          </div>
          <div>
            <h2 className="font-semibold text-card-foreground">{service}</h2>
            <p className="mt-1 text-sm text-muted-foreground">{description}</p>
          </div>
        </div>

        <div className="space-y-4">{children}</div>
        <div className="flex justify-end gap-2 border-t border-border pt-5">
          <Button type="button" variant="outline">
            <PlugZapIcon aria-hidden="true" />
            接続テスト
          </Button>
          <Button type="button">
            <SaveIcon aria-hidden="true" />
            保存
          </Button>
        </div>
      </fieldset>
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center bg-background/75 backdrop-grayscale"
      >
        <span className="rounded-full border border-border bg-background px-4 py-2 text-sm font-semibold text-foreground shadow-sm">
          Coming Soon
        </span>
      </div>
      <p id={`${service}-coming-soon`} className="sr-only">
        {service}連携はComing Soonです。すべての設定操作は現在無効です。
      </p>
    </section>
  )
}

export default function SettingsPage() {
  return (
    <div className="min-h-svh bg-muted/30">
      <AppSidebar />
      <main className="min-h-svh pl-64">
        <div className="mx-auto max-w-7xl px-10 py-8">
          <AppBreadcrumb
            items={[
              { label: "管理・連携設定", href: "/settings" },
              { label: "連携設定" },
            ]}
          />

          <div className="mt-8">
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              管理・連携設定
            </h1>
            <p className="mt-2 text-sm text-muted-foreground">
              外部サービスとの連携設定と接続状況を確認できます。
            </p>
          </div>

          <section className="mt-8" aria-labelledby="integration-settings-heading">
            <div className="mb-4 flex items-center gap-2">
              <Rows3Icon aria-hidden="true" className="size-5 text-muted-foreground" />
              <h2 id="integration-settings-heading" className="text-lg font-semibold">
                連携設定
              </h2>
            </div>
            <div className="grid grid-cols-3 gap-5">
              <IntegrationCard
                service="Backlog"
                description="BacklogのドメインとAPIキーを設定します。"
                icon={KeyRoundIcon}
              >
                <label className="grid gap-2 text-sm font-medium" htmlFor="backlog-domain">
                  ドメイン
                  <Input id="backlog-domain" placeholder="example.backlog.com" />
                </label>
                <label className="grid gap-2 text-sm font-medium" htmlFor="backlog-api-key">
                  APIキー
                  <Input id="backlog-api-key" type="password" placeholder="APIキーを入力" />
                </label>
              </IntegrationCard>

              <IntegrationCard
                service="Slack"
                description="Slack Incoming Webhook URLを設定します。"
                icon={MessageSquareMoreIcon}
              >
                <label className="grid gap-2 text-sm font-medium" htmlFor="slack-webhook-url">
                  Webhook URL
                  <Input
                    id="slack-webhook-url"
                    type="url"
                    placeholder="https://hooks.slack.com/..."
                  />
                </label>
              </IntegrationCard>

              <IntegrationCard
                service="Googleカレンダー"
                description="連携するGoogleアカウントとカレンダーを選択します。"
                icon={CalendarDaysIcon}
              >
                <label className="grid gap-2 text-sm font-medium" htmlFor="google-account">
                  アカウント
                  <Input id="google-account" type="email" placeholder="example@gmail.com" />
                </label>
                <label className="grid gap-2 text-sm font-medium" htmlFor="google-calendar">
                  カレンダー
                  <select
                    id="google-calendar"
                    defaultValue=""
                    className="h-8 w-full rounded-lg border border-input bg-background px-2.5 text-sm"
                  >
                    <option value="">カレンダーを選択</option>
                  </select>
                </label>
              </IntegrationCard>
            </div>
          </section>

          <section className="mt-10" aria-labelledby="connection-history-heading">
            <div className="mb-4 flex items-center gap-2">
              <SendIcon aria-hidden="true" className="size-5 text-muted-foreground" />
              <h2 id="connection-history-heading" className="text-lg font-semibold">
                接続履歴
              </h2>
            </div>
            <div className="rounded-xl border border-border bg-card px-5">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>サービス</TableHead>
                    <TableHead>最終接続確認</TableHead>
                    <TableHead>ステータス</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {connectionHistory.map((connection) => (
                    <TableRow key={connection.service}>
                      <TableCell className="font-medium">{connection.service}</TableCell>
                      <TableCell>{connection.lastChecked}</TableCell>
                      <TableCell>
                        <span className="rounded-full bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground">
                          {connection.status}
                        </span>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </section>
        </div>
      </main>
    </div>
  )
}
