"use client";

import { Alert } from "@/components/ui/Alert";
import { Modal } from "@/components/ui/Modal";
import { isClosed } from "@/lib/domain/workflow";
import type { ServiceRequest } from "@/types/request";
import { useT } from "@/providers/LocaleProvider";
import { MessageForm } from "./MessageForm";
import { RequestDetails } from "./RequestDetails";

interface CustomerRequestModalProps {
  request: ServiceRequest | null;
  onClose: () => void;
  onChanged: (updated: ServiceRequest) => void;
}

export function CustomerRequestModal({ request, onClose, onChanged }: CustomerRequestModalProps) {
  const t = useT();
  return (
    <Modal isOpen={request !== null} onClose={onClose} title={t("request.detail.title")} size="lg">
      {request && (
        <div className="space-y-6">
          <RequestDetails request={request} />
          {isClosed(request.status) ? (
            <Alert tone="info">{t("request.detail.reply.closedNote")}</Alert>
          ) : (
            <MessageForm
              requestId={request.id}
              visibility="public"
              label={t("request.detail.reply.label")}
              placeholder={t("request.detail.reply.placeholder")}
              sendLabel={t("request.detail.reply.send")}
              sentMessage={t("request.detail.reply.sent")}
              onSent={onChanged}
            />
          )}
        </div>
      )}
    </Modal>
  );
}
