import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import {
  DataTable,
  type DataTableColumn,
  type DataTableSortState,
} from "./data-table"

type Person = { id: string; name: string; age: number }

const columns: DataTableColumn<Person>[] = [
  { id: "name", header: "名前", cell: (person) => person.name, sortable: true },
  { id: "age", header: "年齢", cell: (person) => person.age },
]

describe("DataTable", () => {
  afterEach(() => {
    cleanup()
    vi.useRealTimers()
  })

  it("列と親から渡された行データをそのまま描画し、差し替えを反映する", () => {
    const { rerender } = render(
      <DataTable columns={columns} data={[{ id: "1", name: "太郎", age: 20 }]} getRowKey={(row) => row.id} />
    )

    expect(screen.getByText("太郎")).toBeInTheDocument()
    expect(screen.getByText("20")).toBeInTheDocument()

    rerender(
      <DataTable columns={columns} data={[{ id: "2", name: "花子", age: 30 }]} getRowKey={(row) => row.id} />
    )

    expect(screen.queryByText("太郎")).not.toBeInTheDocument()
    expect(screen.getByText("花子")).toBeInTheDocument()
  })

  it("検索入力を300msデバウンスし、最新値と対象列だけを通知する", () => {
    vi.useFakeTimers()
    const onChange = vi.fn()
    render(
      <DataTable
        columns={columns}
        data={[]}
        search={{ value: "", columns: ["name"], placeholder: "名前で検索", onChange }}
      />
    )

    const input = screen.getByPlaceholderText("名前で検索")
    fireEvent.change(input, { target: { value: "た" } })
    vi.advanceTimersByTime(299)
    expect(onChange).not.toHaveBeenCalled()

    fireEvent.change(input, { target: { value: "太郎" } })
    vi.advanceTimersByTime(300)
    expect(onChange).toHaveBeenCalledTimes(1)
    expect(onChange).toHaveBeenCalledWith("太郎", ["name"])
  })

  it("外部検索値の差し替え時に保留中の古い検索通知を破棄する", async () => {
    vi.useFakeTimers()
    const onChange = vi.fn()
    const { rerender } = render(
      <DataTable
        columns={columns}
        data={[]}
        search={{ value: "", columns: ["name"], placeholder: "名前で検索", onChange }}
      />
    )

    fireEvent.change(screen.getByPlaceholderText("名前で検索"), { target: { value: "古い値" } })
    vi.advanceTimersByTime(100)
    rerender(
      <DataTable
        columns={columns}
        data={[]}
        search={{ value: "新しい値", columns: ["name"], placeholder: "名前で検索", onChange }}
      />
    )

    await vi.advanceTimersByTimeAsync(300)
    expect(onChange).not.toHaveBeenCalled()
    expect(screen.getByPlaceholderText("名前で検索")).toHaveValue("新しい値")
  })

  it("ソート状態を昇順、降順、未指定の順に通知し、支援技術へ状態を伝える", () => {
    const onChange = vi.fn()
    const { rerender } = render(
      <DataTable columns={columns} data={[]} sort={{ value: null, onChange }} />
    )

    const button = screen.getByRole("button", { name: "「name」で並び替え" })
    fireEvent.click(button)
    expect(onChange).toHaveBeenLastCalledWith({ columnId: "name", direction: "asc" })

    const ascending: DataTableSortState = { columnId: "name", direction: "asc" }
    rerender(<DataTable columns={columns} data={[]} sort={{ value: ascending, onChange }} />)
    expect(screen.getByRole("columnheader", { name: "名前" })).toHaveAttribute("aria-sort", "ascending")
    fireEvent.keyDown(screen.getByRole("button", { name: "「name」で並び替え" }), { key: "Enter" })
    expect(onChange).toHaveBeenLastCalledWith({ columnId: "name", direction: "desc" })

    rerender(<DataTable columns={columns} data={[]} sort={{ value: { columnId: "name", direction: "desc" }, onChange }} />)
    expect(screen.getByRole("columnheader", { name: "名前" })).toHaveAttribute("aria-sort", "descending")
    fireEvent.keyDown(screen.getByRole("button", { name: "「name」で並び替え" }), { key: " " })
    expect(onChange).toHaveBeenLastCalledWith(null)
    expect(screen.queryByRole("button", { name: "「age」で並び替え" })).not.toBeInTheDocument()
  })

  it("loading、error、再試行、空状態を表示する", () => {
    const { rerender } = render(<DataTable columns={columns} data={[]} loading />)
    expect(screen.getAllByLabelText("読み込み中")).toHaveLength(3)

    const onRetry = vi.fn()
    rerender(<DataTable columns={columns} data={[]} error="取得に失敗しました" onRetry={onRetry} />)
    fireEvent.click(screen.getByRole("button", { name: "再試行" }))
    expect(onRetry).toHaveBeenCalledTimes(1)

    rerender(<DataTable columns={columns} data={[]} emptyMessage="対象なし" />)
    expect(screen.getByText("対象なし")).toBeInTheDocument()
  })
})
