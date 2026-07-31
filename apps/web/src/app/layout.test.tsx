import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, expect, test, vi } from "vitest"

const toasterMock = vi.hoisted(() => vi.fn(() => <div data-testid="toaster" />))

vi.mock("@/components/ui/sonner", () => ({ Toaster: toasterMock }))

import RootLayout from "./layout"

afterEach(cleanup)

test("アプリ全体用のToasterをbody配下へ1回配置する", () => {
  render(
    <RootLayout>
      <main>ページ内容</main>
    </RootLayout>
  )

  expect(screen.getByTestId("toaster")).toBeInTheDocument()
  expect(screen.getAllByTestId("toaster")).toHaveLength(1)
  expect(toasterMock).toHaveBeenCalledOnce()
})
