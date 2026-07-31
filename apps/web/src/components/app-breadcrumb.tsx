import { Fragment, type ReactNode } from "react"
import Link from "next/link"

import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"

export type AppBreadcrumbItem = {
  label: ReactNode
  href?: string
}

export function AppBreadcrumb({
  items,
}: {
  items: readonly AppBreadcrumbItem[]
}) {
  return (
    <Breadcrumb>
      <BreadcrumbList>
        {items.map((item, index) => {
          const isCurrentPage = index === items.length - 1

          return (
            <Fragment key={`${item.href ?? "current"}-${index}`}>
              <BreadcrumbItem>
                {isCurrentPage ? (
                  <BreadcrumbPage>{item.label}</BreadcrumbPage>
                ) : item.href ? (
                  <BreadcrumbLink asChild>
                    <Link href={item.href}>{item.label}</Link>
                  </BreadcrumbLink>
                ) : (
                  <span>{item.label}</span>
                )}
              </BreadcrumbItem>
              {!isCurrentPage && <BreadcrumbSeparator />}
            </Fragment>
          )
        })}
      </BreadcrumbList>
    </Breadcrumb>
  )
}
