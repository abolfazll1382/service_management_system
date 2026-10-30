"use client";

import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Send } from "lucide-react";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { TextareaField } from "@/components/ui/FormField";
import { useErrorMessage } from "@/hooks/useErrorMessage";
import { useRevalidateOnLocaleChange } from "@/hooks/useRevalidateOnLocaleChange";
import { requestsApi } from "@/lib/api";
import { createMessageSchema, type MessageInput } from "@/lib/validation/request";
import type { MessageVisibility, ServiceRequest } from "@/types/request";
import { useT } from "@/providers/LocaleProvider";
import { useToast } from "@/providers/ToastProvider";

interface MessageFormProps {
  requestId: string;
  /** Fixed for applicants; staff pick between a public reply and an internal note. */
  visibility: MessageVisibility | "choose";
  label: string;
  placeholder: string;
  sendLabel: string;
  sentMessage: string;
  onSent: (updated: ServiceRequest) => void;
}

export function MessageForm({ requestId, visibility, label, placeholder, sendLabel, sentMessage, onSent }: MessageFormProps) {
  const t = useT();
  const toast = useToast();
  const errorMessage = useErrorMessage();
  const [formError, setFormError] = useState<string | null>(null);

  const schema = useMemo(() => createMessageSchema(t), [t]);
  const form = useForm<MessageInput>({
    resolver: zodResolver(schema),
    defaultValues: { body: "", visibility: visibility === "choose" ? "public" : visibility },
  });
  const { register, handleSubmit, reset, formState } = form;
  const { errors, isSubmitting } = formState;
  useRevalidateOnLocaleChange(form);

  const send = handleSubmit(async (values) => {
    setFormError(null);
    try {
      const updated = await requestsApi.addMessage(requestId, values);
      reset({ body: "", visibility: values.visibility });
      toast.success(sentMessage);
      onSent(updated);
    } catch (error) {
      setFormError(errorMessage(error));
    }
  });

  return (
    <form onSubmit={send} noValidate className="space-y-3">
      {formError && <Alert tone="danger">{formError}</Alert>}
      {visibility === "choose" && (
        <fieldset>
          <legend className="mb-1.5 text-sm font-medium text-ink-800">{t("staff.work.message.visibility")}</legend>
          <div className="flex flex-wrap gap-x-5 gap-y-1.5 text-sm text-ink-800">
            {(["public", "internal"] as const).map((value) => (
              <label key={value} className="flex items-center gap-2">
                <input type="radio" value={value} className="h-4 w-4 accent-tile-700" {...register("visibility")} />
                {t(`staff.work.message.${value}`)}
              </label>
            ))}
          </div>
        </fieldset>
      )}
      <TextareaField
        id={`message-${requestId}`}
        label={label}
        placeholder={placeholder}
        rows={3}
        error={errors.body?.message}
        {...register("body")}
      />
      <Button type="submit" size="sm" isLoading={isSubmitting}>
        <Send className="h-4 w-4 rtl:-scale-x-100" aria-hidden="true" />
        {sendLabel}
      </Button>
    </form>
  );
}
