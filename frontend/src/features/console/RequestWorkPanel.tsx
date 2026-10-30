"use client";

import { useCallback, useMemo, useState, type ReactNode } from "react";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { UserCheck, UserMinus } from "lucide-react";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { Select } from "@/components/ui/Select";
import { SelectField, TextareaField } from "@/components/ui/FormField";
import { MessageForm } from "@/features/requests/MessageForm";
import { RequestDetails } from "@/features/requests/RequestDetails";
import { useAsync } from "@/hooks/useAsync";
import { useErrorMessage } from "@/hooks/useErrorMessage";
import { useRevalidateOnLocaleChange } from "@/hooks/useRevalidateOnLocaleChange";
import { useCan, useSession } from "@/hooks/useSession";
import { requestsApi } from "@/lib/api";
import { canAssignTo } from "@/lib/auth/policies";
import { isClosed, nextStatuses, requiresNote } from "@/lib/domain/workflow";
import { createTransitionSchema, type TransitionInput } from "@/lib/validation/request";
import type { ServiceRequest } from "@/types/request";
import { useLocale, useT } from "@/providers/LocaleProvider";
import { useToast } from "@/providers/ToastProvider";

interface WorkPanelProps {
  request: ServiceRequest | null;
  onClose: () => void;
  /** Called with the server's version after every change, so the list and panel stay in step. */
  onChanged: (updated: ServiceRequest) => void;
}

function Block({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-xl border border-ink-200 bg-ink-50/50 p-4">
      <h3 className="mb-3 text-sm font-bold text-ink-900">{title}</h3>
      {children}
    </section>
  );
}

/**
 * Where a request is actually processed. Every control here is offered only
 * if the policy allows it, but that is a courtesy: the server checks again
 * and refuses anything outside the caller's departments.
 */
export function RequestWorkPanel({ request, onClose, onChanged }: WorkPanelProps) {
  const t = useT();
  return (
    <Modal isOpen={request !== null} onClose={onClose} title={t("staff.work.title")} size="xl">
      {request && <PanelBody key={request.id} request={request} onChanged={onChanged} />}
    </Modal>
  );
}

function PanelBody({ request, onChanged }: { request: ServiceRequest; onChanged: (updated: ServiceRequest) => void }) {
  const t = useT();
  const closed = isClosed(request.status);
  const can = useCan();
  const resource = { departmentId: request.departmentId };

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_21rem]">
      <RequestDetails request={request} showApplicant />
      <div className="space-y-4 lg:sticky lg:top-0 lg:self-start">
        {closed && <Alert tone="info">{t("request.detail.reply.closedNote")}</Alert>}
        {!closed && can("request.transition", resource) && <StatusBlock request={request} onChanged={onChanged} />}
        {!closed && can("request.assign", resource) && <AssignmentBlock request={request} onChanged={onChanged} />}
        {!closed && (
          <Block title={t("staff.work.message.label")}>
            <MessageForm
              requestId={request.id}
              visibility="choose"
              label={t("staff.work.message.body")}
              placeholder={t("staff.work.message.placeholder")}
              sendLabel={t("staff.work.message.send")}
              sentMessage={t("staff.work.toasts.messageAdded")}
              onSent={onChanged}
            />
          </Block>
        )}
      </div>
    </div>
  );
}

function StatusBlock({ request, onChanged }: { request: ServiceRequest; onChanged: (updated: ServiceRequest) => void }) {
  const t = useT();
  const toast = useToast();
  const errorMessage = useErrorMessage();
  const [formError, setFormError] = useState<string | null>(null);
  const options = nextStatuses(request.status);

  const schema = useMemo(() => createTransitionSchema(t), [t]);
  const form = useForm<TransitionInput>({ resolver: zodResolver(schema), defaultValues: { to: undefined, note: "" } });
  const { register, handleSubmit, control, reset, formState } = form;
  const { errors, isSubmitting } = formState;
  useRevalidateOnLocaleChange(form);
  const target = useWatch({ control, name: "to" });

  const apply = handleSubmit(async (values) => {
    setFormError(null);
    try {
      const updated = await requestsApi.transition(request.id, values);
      reset({ to: undefined, note: "" });
      toast.success(t("staff.work.toasts.statusUpdated"));
      onChanged(updated);
    } catch (error) {
      setFormError(errorMessage(error));
    }
  });

  return (
    <Block title={t("staff.work.status.label")}>
      {options.length === 0 ? (
        <p className="text-sm text-ink-600">{t("staff.work.status.none")}</p>
      ) : (
        <form onSubmit={apply} noValidate className="space-y-3">
          {formError && <Alert tone="danger">{formError}</Alert>}
          <SelectField
            id={`status-${request.id}`}
            label={t("staff.work.status.next")}
            error={errors.to?.message ? t("validation.select") : undefined}
            {...register("to", { setValueAs: (value: string) => (value === "" ? undefined : value) })}
          >
            <option value="">{t("staff.work.status.placeholder")}</option>
            {options.map((status) => (
              <option key={status} value={status}>
                {t(`common.status.${status}`)}
              </option>
            ))}
          </SelectField>
          <TextareaField
            id={`note-${request.id}`}
            label={t("staff.work.status.note")}
            hint={t("staff.work.status.noteHint")}
            rows={3}
            required={target !== undefined && requiresNote(target)}
            optional={target === undefined || !requiresNote(target)}
            error={errors.note?.message}
            {...register("note")}
          />
          <Button type="submit" size="sm" isLoading={isSubmitting}>
            {t("staff.work.status.apply")}
          </Button>
        </form>
      )}
    </Block>
  );
}

function AssignmentBlock({ request, onChanged }: { request: ServiceRequest; onChanged: (updated: ServiceRequest) => void }) {
  const t = useT();
  const { locale } = useLocale();
  const toast = useToast();
  const errorMessage = useErrorMessage();
  const { user } = useSession();
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [chosen, setChosen] = useState("");

  const loadStaff = useCallback(() => requestsApi.assignableStaff(request.departmentId), [request.departmentId]);
  const { data: staff } = useAsync(loadStaff);

  if (!user) return null;
  const isAdmin = user.role === "admin";
  const mine = request.assignee?.id === user.id;
  const canClaim = !mine && canAssignTo(user, user, request.departmentId);

  const assign = async (assigneeId: string | null) => {
    setBusy(true);
    setFormError(null);
    try {
      const updated = await requestsApi.assign(request.id, assigneeId);
      setChosen("");
      toast.success(t("staff.work.toasts.assigned"));
      onChanged(updated);
    } catch (error) {
      setFormError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Block title={t("staff.work.assignment.title")}>
      <div className="space-y-3">
        {formError && <Alert tone="danger">{formError}</Alert>}
        <p className="text-sm text-ink-700">
          {request.assignee ? request.assignee.name[locale] : <span className="text-ink-500">{t("request.detail.unassigned")}</span>}
        </p>
        <div className="flex flex-wrap gap-2">
          {canClaim && (
            <Button size="sm" variant="outline" disabled={busy} onClick={() => assign(user.id)}>
              <UserCheck className="h-4 w-4" aria-hidden="true" />
              {t("staff.work.assignment.assignToMe")}
            </Button>
          )}
          {request.assignee && (
            <Button size="sm" variant="ghost" disabled={busy} onClick={() => assign(null)}>
              <UserMinus className="h-4 w-4" aria-hidden="true" />
              {t("staff.work.assignment.unassign")}
            </Button>
          )}
        </div>
        {isAdmin && (
          <div className="flex items-center gap-2">
            <label htmlFor={`assignee-${request.id}`} className="sr-only">
              {t("staff.work.assignment.assignTo")}
            </label>
            <div className="min-w-0 flex-1">
              <Select id={`assignee-${request.id}`} value={chosen} onChange={(event) => setChosen(event.target.value)}>
                <option value="">{t("staff.work.assignment.assignTo")}</option>
                {(staff ?? []).map((member) => (
                  <option key={member.id} value={member.id}>
                    {member.name[locale]}
                  </option>
                ))}
              </Select>
            </div>
            <Button size="sm" disabled={busy || chosen === ""} onClick={() => assign(chosen)}>
              {t("staff.work.assignment.assign")}
            </Button>
          </div>
        )}
      </div>
    </Block>
  );
}
