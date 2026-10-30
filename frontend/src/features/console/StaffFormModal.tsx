"use client";

import { useMemo, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/FormField";
import { Ltr } from "@/components/ui/Ltr";
import { Modal } from "@/components/ui/Modal";
import { Switch } from "@/components/ui/Switch";
import { useErrorMessage } from "@/hooks/useErrorMessage";
import { useRevalidateOnLocaleChange } from "@/hooks/useRevalidateOnLocaleChange";
import { staffApi } from "@/lib/api";
import {
  createStaffInputSchema,
  updateStaffInputSchema,
  type CreateStaffInput,
  type UpdateStaffInput,
} from "@/lib/validation/staff";
import { ApiError } from "@/types/api";
import type { StaffProfile } from "@/types/user";
import { useLocale, useT } from "@/providers/LocaleProvider";
import { useToast } from "@/providers/ToastProvider";
import { DepartmentChecklist } from "./DepartmentChecklist";

export type StaffFormTarget = { mode: "create" } | { mode: "edit"; member: StaffProfile };

interface StaffFormModalProps {
  target: StaffFormTarget | null;
  onClose: () => void;
  /** Called after the server accepted the change, so the list can refetch. */
  onSaved: () => void;
}

export function StaffFormModal({ target, onClose, onSaved }: StaffFormModalProps) {
  const t = useT();
  return (
    <Modal
      isOpen={target !== null}
      onClose={onClose}
      title={target?.mode === "edit" ? t("staff.team.form.editTitle") : t("staff.team.form.createTitle")}
    >
      {target?.mode === "create" && <CreateForm onClose={onClose} onSaved={onSaved} />}
      {target?.mode === "edit" && <EditForm key={target.member.id} member={target.member} onClose={onClose} onSaved={onSaved} />}
    </Modal>
  );
}

interface FormProps {
  onClose: () => void;
  onSaved: () => void;
}

function CreateForm({ onClose, onSaved }: FormProps) {
  const t = useT();
  const toast = useToast();
  const errorMessage = useErrorMessage();
  const [formError, setFormError] = useState<string | null>(null);

  const schema = useMemo(() => createStaffInputSchema(t), [t]);
  const form = useForm<CreateStaffInput>({
    resolver: zodResolver(schema),
    defaultValues: { nameFa: "", nameEn: "", username: "", password: "", departmentIds: [] },
  });
  const { register, handleSubmit, control, setError, formState } = form;
  const { errors, isSubmitting } = formState;
  useRevalidateOnLocaleChange(form);

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      await staffApi.create(values);
      toast.success(t("staff.team.toasts.created"));
      onSaved();
      onClose();
    } catch (error) {
      if (error instanceof ApiError && error.code === "username_taken") {
        setError("username", { message: t("errors.username_taken") });
      } else {
        setFormError(errorMessage(error));
      }
    }
  });

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-4">
      {formError && <Alert tone="danger">{formError}</Alert>}
      <div className="grid gap-4 sm:grid-cols-2">
        <TextField
          id="staff-name-fa"
          label={t("staff.team.form.nameFa")}
          dir="rtl"
          required
          error={errors.nameFa?.message}
          {...register("nameFa")}
        />
        <TextField
          id="staff-name-en"
          label={t("staff.team.form.nameEn")}
          dir="ltr"
          required
          error={errors.nameEn?.message}
          {...register("nameEn")}
        />
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <TextField
          id="staff-username"
          label={t("common.fields.username")}
          hint={t("staff.team.form.usernameHint")}
          dir="ltr"
          autoCapitalize="none"
          spellCheck={false}
          required
          error={errors.username?.message}
          // "Reza" and "reza" are the same person; fold case so the format rule only flags real mistakes.
          {...register("username", { setValueAs: (value: string) => value.trim().toLowerCase() })}
        />
        <TextField
          id="staff-password"
          type="password"
          label={t("common.fields.password")}
          hint={t("staff.team.form.passwordHint")}
          dir="ltr"
          autoComplete="new-password"
          required
          error={errors.password?.message}
          {...register("password")}
        />
      </div>
      <Controller
        control={control}
        name="departmentIds"
        render={({ field }) => (
          <DepartmentChecklist
            legend={t("staff.team.form.departments")}
            value={field.value}
            onChange={field.onChange}
            error={errors.departmentIds?.message}
          />
        )}
      />
      <div className="flex justify-end gap-2 pt-2">
        <Button variant="outline" onClick={onClose} disabled={isSubmitting}>
          {t("common.actions.cancel")}
        </Button>
        <Button type="submit" isLoading={isSubmitting}>
          {t("staff.team.form.create")}
        </Button>
      </div>
    </form>
  );
}

function EditForm({ member, onClose, onSaved }: FormProps & { member: StaffProfile }) {
  const t = useT();
  const { locale } = useLocale();
  const toast = useToast();
  const errorMessage = useErrorMessage();
  const [formError, setFormError] = useState<string | null>(null);

  const schema = useMemo(() => updateStaffInputSchema(t), [t]);
  const form = useForm<UpdateStaffInput>({
    resolver: zodResolver(schema),
    defaultValues: { departmentIds: [...member.departmentIds], isActive: member.isActive },
  });
  const { handleSubmit, control, formState } = form;
  const { errors, isSubmitting } = formState;
  useRevalidateOnLocaleChange(form);

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      await staffApi.update(member.id, values);
      toast.success(t("staff.team.toasts.updated"));
      onSaved();
      onClose();
    } catch (error) {
      setFormError(errorMessage(error));
    }
  });

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-4">
      {formError && <Alert tone="danger">{formError}</Alert>}
      <p className="text-sm text-ink-700">
        <span className="font-semibold text-ink-950">{member.name[locale]}</span> · <Ltr>{member.username}</Ltr>
      </p>
      <Controller
        control={control}
        name="departmentIds"
        render={({ field }) => (
          <DepartmentChecklist
            legend={t("staff.team.form.departments")}
            value={field.value}
            onChange={field.onChange}
            error={errors.departmentIds?.message}
          />
        )}
      />
      <Controller
        control={control}
        name="isActive"
        render={({ field }) => (
          <div className="flex items-start justify-between gap-4 rounded-lg border border-ink-200 p-3">
            <div className="min-w-0">
              <p className="text-sm font-medium text-ink-900">{t("staff.team.form.active")}</p>
              <p className="mt-0.5 text-sm text-ink-500">{t("staff.team.form.activeHint")}</p>
            </div>
            <Switch checked={field.value} onChange={field.onChange} label={t("staff.team.form.active")} />
          </div>
        )}
      />
      <div className="flex justify-end gap-2 pt-2">
        <Button variant="outline" onClick={onClose} disabled={isSubmitting}>
          {t("common.actions.cancel")}
        </Button>
        <Button type="submit" isLoading={isSubmitting}>
          {t("common.actions.save")}
        </Button>
      </div>
    </form>
  );
}
