"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { ClipboardCheckIcon, ListChecksIcon, SettingsIcon } from "lucide-react"

import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
} from "@/components/ui/sidebar"

const navigationItems = [
  {
    title: "チェックリスト一覧",
    href: "/",
    icon: ListChecksIcon,
  },
  {
    title: "管理・連携設定",
    href: "/settings",
    icon: SettingsIcon,
  },
]

export function AppSidebar() {
  const pathname = usePathname()

  return (
    <SidebarProvider>
      <Sidebar
        collapsible="none"
        className="fixed inset-y-0 z-10 hidden h-svh border-r border-sidebar-border md:flex"
      >
        <SidebarHeader>
          <Link
            href="/"
            className="flex items-center gap-2 rounded-md px-2 py-1 text-lg font-semibold text-sidebar-foreground focus-visible:ring-2 focus-visible:ring-sidebar-ring focus-visible:outline-hidden"
          >
            <ClipboardCheckIcon aria-hidden="true" className="size-5" />
            <span>PrepFlow</span>
          </Link>
        </SidebarHeader>
        <SidebarContent>
          <SidebarGroup>
            <SidebarGroupContent>
              <SidebarMenu>
                {navigationItems.map((item) => (
                  <SidebarMenuItem key={item.href}>
                    <SidebarMenuButton
                      asChild
                      isActive={pathname === item.href}
                    >
                      <Link
                        href={item.href}
                        aria-current={pathname === item.href ? "page" : undefined}
                      >
                        <item.icon aria-hidden="true" />
                        <span>{item.title}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        </SidebarContent>
      </Sidebar>
    </SidebarProvider>
  )
}
