import { cleanup, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import type { ComponentProps } from "react"
import { afterEach, expect, test, vi } from "vitest"

const navigationMock = vi.hoisted(() => ({ pathname: "/" }))

vi.mock("next/link", () => ({
  default: ({ children, ...props }: ComponentProps<"a">) => (
    <a {...props}>{children}</a>
  ),
}))

vi.mock("next/navigation", () => ({
  usePathname: () => navigationMock.pathname,
}))

import { AppBreadcrumb } from "@/components/app-breadcrumb"
import { AppSidebar } from "@/components/app-sidebar"

afterEach(() => {
  cleanup()
  navigationMock.pathname = "/"
})

test("AppSidebar marks only the exact pathname as the current page", () => {
  navigationMock.pathname = "/settings"

  render(<AppSidebar />)

  expect(
    screen.getByRole("link", { name: "管理・連携設定" })
  ).toHaveAttribute("aria-current", "page")
  expect(screen.getByRole("link", { name: "チェックリスト一覧" })).not.toHaveAttribute(
    "aria-current"
  )
})

test("AppSidebar navigation links can receive keyboard focus", async () => {
  const user = userEvent.setup()

  render(<AppSidebar />)

  await user.tab()
  await user.tab()

  expect(screen.getByRole("link", { name: "チェックリスト一覧" })).toHaveFocus()
})

test("AppBreadcrumb renders links, the current page, and separators without a home item", () => {
  render(
    <AppBreadcrumb
      items={[
        { label: "チェックリスト一覧", href: "/" },
        { label: "詳細", href: "/checklists/1" },
        { label: "準備状況" },
      ]}
    />
  )

  expect(screen.getByRole("link", { name: "チェックリスト一覧" })).toHaveAttribute(
    "href",
    "/"
  )
  expect(screen.getByRole("link", { name: "詳細" })).toHaveAttribute(
    "href",
    "/checklists/1"
  )
  expect(screen.getByText("準備状況")).toHaveAttribute("aria-current", "page")
  expect(screen.queryByRole("link", { name: /ホーム/i })).not.toBeInTheDocument()
  expect(
    document.querySelectorAll('[data-slot="breadcrumb-separator"]')
  ).toHaveLength(2)
})
