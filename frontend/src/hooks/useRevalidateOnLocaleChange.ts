"use client";

import { useEffect, useRef } from "react";
import type { FieldValues, Path, UseFormReturn } from "react-hook-form";
import { useLocale } from "@/providers/LocaleProvider";

/**
 * Validation messages are produced when a field is validated, so switching
 * language while an error is on screen would leave it in the old language.
 * This re-validates the fields that currently show an error, once, after
 * the language changes — values the person typed are never touched.
 */
export function useRevalidateOnLocaleChange<Values extends FieldValues>(form: UseFormReturn<Values>) {
  const { locale } = useLocale();
  const previous = useRef(locale);

  useEffect(() => {
    if (previous.current === locale) return;
    previous.current = locale;
    const failing = Object.keys(form.formState.errors) as Path<Values>[];
    if (failing.length > 0) void form.trigger(failing);
  }, [locale, form]);
}
