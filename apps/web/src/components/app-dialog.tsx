"use client"

import type { ReactElement, ReactNode } from "react"

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"

type AppDialogSize = "sm" | "md" | "lg"

type AppDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  trigger?: ReactElement
  title: ReactNode
  description?: ReactNode
  children: ReactNode
  footer?: ReactNode
  size?: AppDialogSize
}

const sizeClasses: Record<AppDialogSize, string> = {
  sm: "max-w-sm sm:max-w-sm",
  md: "max-w-md sm:max-w-md",
  lg: "max-w-lg sm:max-w-lg",
}

function AppDialog({
  open,
  onOpenChange,
  trigger,
  title,
  description,
  children,
  footer,
  size = "md",
}: AppDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {trigger && <DialogTrigger asChild>{trigger}</DialogTrigger>}
      <DialogContent className={sizeClasses[size]}>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description && <DialogDescription>{description}</DialogDescription>}
        </DialogHeader>
        {children}
        {footer && <DialogFooter>{footer}</DialogFooter>}
      </DialogContent>
    </Dialog>
  )
}

export { AppDialog }
export type { AppDialogProps, AppDialogSize }
