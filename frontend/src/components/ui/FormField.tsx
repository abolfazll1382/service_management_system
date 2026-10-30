import { type ReactNode, type TextareaHTMLAttributes, type SelectHTMLAttributes, forwardRef } from "react";
import { cn } from "@/lib/utils/cn";
import { useT } from "@/providers/LocaleProvider";
import { Input, type InputProps } from "./Input";
import { Select } from "./Select";
import { Textarea } from "./Textarea";

interface FieldMeta {
  /** Becomes the control's `id`, and the prefix of the hint/error ids. */
  id: string;
  label: string;
  error?: string;
  hint?: string;
  required?: boolean;
  /** Shows "(optional)" next to the label. */
  optional?: boolean;
  className?: string;
}

function describedBy(id: string, error?: string, hint?: string): string | undefined {
  if (error) return `${id}-error`;
  if (hint) return `${id}-hint`;
  return undefined;
}

/** Label + control + hint/error, wired together for assistive technology. */
export function FormField({ id, label, error, hint, required, optional, className, children }: FieldMeta & { children: ReactNode }) {
  const t = useT();
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <label htmlFor={id} className="text-sm font-medium text-ink-800">
        {label}
        {required && (
          <span className="ms-0.5 text-rose-600" aria-hidden="true">
            *
          </span>
        )}
        {optional && <span className="ms-1.5 text-xs font-normal text-ink-500">({t("common.state.optional")})</span>}
      </label>
      {children}
      {error ? (
        <p id={`${id}-error`} role="alert" className="text-sm text-rose-700">
          {error}
        </p>
      ) : hint ? (
        <p id={`${id}-hint`} className="text-sm text-ink-500">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

type TextFieldProps = FieldMeta & Omit<InputProps, "id" | "invalid">;

/** FormField + Input. Spread react-hook-form's `register(...)` straight onto it. */
export const TextField = forwardRef<HTMLInputElement, TextFieldProps>(
  ({ id, label, error, hint, required, optional, className, ...input }, ref) => (
    <FormField id={id} label={label} error={error} hint={hint} required={required} optional={optional} className={className}>
      <Input
        ref={ref}
        id={id}
        invalid={Boolean(error)}
        aria-describedby={describedBy(id, error, hint)}
        aria-required={required || undefined}
        {...input}
      />
    </FormField>
  ),
);
TextField.displayName = "TextField";

type TextareaFieldProps = FieldMeta & Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "id">;

export const TextareaField = forwardRef<HTMLTextAreaElement, TextareaFieldProps>(
  ({ id, label, error, hint, required, optional, className, ...textarea }, ref) => (
    <FormField id={id} label={label} error={error} hint={hint} required={required} optional={optional} className={className}>
      <Textarea
        ref={ref}
        id={id}
        invalid={Boolean(error)}
        aria-describedby={describedBy(id, error, hint)}
        aria-required={required || undefined}
        {...textarea}
      />
    </FormField>
  ),
);
TextareaField.displayName = "TextareaField";

type SelectFieldProps = FieldMeta & Omit<SelectHTMLAttributes<HTMLSelectElement>, "id">;

export const SelectField = forwardRef<HTMLSelectElement, SelectFieldProps>(
  ({ id, label, error, hint, required, optional, className, children, ...select }, ref) => (
    <FormField id={id} label={label} error={error} hint={hint} required={required} optional={optional} className={className}>
      <Select
        ref={ref}
        id={id}
        invalid={Boolean(error)}
        aria-describedby={describedBy(id, error, hint)}
        aria-required={required || undefined}
        {...select}
      >
        {children}
      </Select>
    </FormField>
  ),
);
SelectField.displayName = "SelectField";
