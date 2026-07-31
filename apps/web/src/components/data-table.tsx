"use client"

import * as React from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

export type DataTableColumn<TData> = {
  id: string
  header: React.ReactNode
  cell: (row: TData) => React.ReactNode
  sortable?: boolean
}

export type DataTableSortState = {
  columnId: string
  direction: "asc" | "desc"
}

export type DataTableSearchProps = {
  value: string
  columns: string[]
  placeholder?: string
  onChange: (value: string, columns: string[]) => void
}

export type DataTableSortProps = {
  value: DataTableSortState | null
  onChange: (value: DataTableSortState | null) => void
}

export type DataTableProps<TData> = {
  columns: DataTableColumn<TData>[]
  data: TData[]
  search?: DataTableSearchProps
  sort?: DataTableSortProps
  loading?: boolean
  error?: React.ReactNode
  onRetry?: () => void
  emptyMessage?: React.ReactNode
  getRowKey?: (row: TData, index: number) => React.Key
  onRowClick?: (row: TData, index: number) => void
}

function nextSortState(
  currentSort: DataTableSortState | null,
  columnId: string
): DataTableSortState | null {
  if (currentSort?.columnId !== columnId) {
    return { columnId, direction: "asc" }
  }

  if (currentSort.direction === "asc") {
    return { columnId, direction: "desc" }
  }

  return null
}

function DataTable<TData>({
  columns,
  data,
  search,
  sort,
  loading = false,
  error,
  onRetry,
  emptyMessage = "データがありません。",
  getRowKey,
  onRowClick,
}: DataTableProps<TData>) {
  const [searchInputValue, setSearchInputValue] = React.useState(
    search?.value ?? ""
  )
  const debounceTimerRef = React.useRef<ReturnType<typeof setTimeout> | null>(
    null
  )
  const searchValue = search?.value ?? ""
  const searchEnabled = Boolean(search)

  React.useEffect(() => {
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current)
      debounceTimerRef.current = null
    }

    let cancelled = false
    queueMicrotask(() => {
      if (!cancelled) {
        setSearchInputValue(searchValue)
      }
    })

    return () => {
      cancelled = true
    }
  }, [searchValue, searchEnabled])

  React.useEffect(() => {
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current)
      }
    }
  }, [])

  const handleSearchChange = (value: string) => {
    setSearchInputValue(value)

    if (!search) {
      return
    }

    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current)
    }

    debounceTimerRef.current = setTimeout(() => {
      search.onChange(value, search.columns)
      debounceTimerRef.current = null
    }, 300)
  }

  const handleSortChange = (columnId: string) => {
    if (sort) {
      sort.onChange(nextSortState(sort.value, columnId))
    }
  }

  return (
    <div className="space-y-4">
      {search ? (
        <Input
          type="search"
          value={searchInputValue}
          placeholder={search.placeholder}
          onChange={(event) => handleSearchChange(event.target.value)}
          aria-label="検索"
        />
      ) : null}

      <Table>
        <TableHeader>
          <TableRow>
            {columns.map((column) => {
              const currentSort =
                sort?.value?.columnId === column.id ? sort.value : null
              const ariaSort = currentSort
                ? currentSort.direction === "asc"
                  ? "ascending"
                  : "descending"
                : undefined

              return (
                <TableHead key={column.id} scope="col" aria-sort={ariaSort}>
                  {column.sortable ? (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => handleSortChange(column.id)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault()
                          handleSortChange(column.id)
                        }
                      }}
                      disabled={!sort}
                      aria-label={`「${column.id}」で並び替え`}
                    >
                      {column.header}
                    </Button>
                  ) : (
                    column.header
                  )}
                </TableHead>
              )
            })}
          </TableRow>
        </TableHeader>
        <TableBody>
          {error ? (
            <TableRow>
              <TableCell colSpan={columns.length} className="py-6 text-center">
                <div className="space-y-3">
                  <p>{error}</p>
                  {onRetry ? (
                    <Button type="button" variant="outline" onClick={onRetry}>
                      再試行
                    </Button>
                  ) : null}
                </div>
              </TableCell>
            </TableRow>
          ) : loading ? (
            Array.from({ length: 3 }, (_, rowIndex) => (
              <TableRow key={`loading-${rowIndex}`} aria-label="読み込み中">
                {columns.map((column) => (
                  <TableCell key={column.id}>
                    <Skeleton className="h-5 w-full" />
                  </TableCell>
                ))}
              </TableRow>
            ))
          ) : data.length === 0 ? (
            <TableRow>
              <TableCell colSpan={columns.length} className="py-6 text-center">
                {emptyMessage}
              </TableCell>
            </TableRow>
          ) : (
            data.map((row, index) => (
              <TableRow
                key={getRowKey?.(row, index) ?? index}
                className={onRowClick ? "cursor-pointer" : undefined}
                onClick={(event) => {
                  if (
                    !onRowClick ||
                    (event.target as HTMLElement).closest(
                      "a, button, input, select, textarea"
                    )
                  ) {
                    return
                  }

                  onRowClick(row, index)
                }}
              >
                {columns.map((column) => (
                  <TableCell key={column.id}>{column.cell(row)}</TableCell>
                ))}
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </div>
  )
}

export { DataTable }
