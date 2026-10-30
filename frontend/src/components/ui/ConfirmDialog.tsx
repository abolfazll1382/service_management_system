"use client";

import type { ReactNode } from "react";
import { useT } from "@/providers/LocaleProvider";
import { Button } from "./Button";
import { Modal } from "./Modal";

interface ConfirmDialogProps {
  isOpen: boolean;
  title: string;
  children: ReactNode;
  confirmLabel: string;
  isLoading?: boolean;
  danger?: boolean;
  onConfirm: () => void;
  onClose: () => void;
}

export function ConfirmDialog({ isOpen, title, children, confirmLabel, isLoading, danger, onConfirm, onClose }: ConfirmDialogProps) {
  const t = useT();
  return (
    <Modal isOpen={isOpen} onClose={onClose} title={title} size="sm">
      <div className="text-sm text-ink-600">{children}</div>
      <div className="mt-6 flex justify-end gap-2">
        <Button variant="outline" onClick={onClose} disabled={isLoading}>
          {t("common.actions.cancel")}
        </Button>
        <Button variant={danger ? "danger" : "primary"} onClick={onConfirm} isLoading={isLoading}>
          {confirmLabel}
        </Button>
      </div>
    </Modal>
  );
}
