import { type TextareaHTMLAttributes, forwardRef } from "react";
import { cn } from "@/lib/utils/cn";
import { controlStyles } from "./Input";

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  invalid?: boolean;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(({ className, invalid, ...props }, ref) => (
  <textarea
    ref={ref}
    aria-invalid={invalid || undefined}
    // Free text may be Persian or Latin: each paragraph takes its direction from what is typed.
    dir="auto"
    className={cn(controlStyles(invalid), "px-3 py-2 leading-7", className)}
    {...props}
  />
));
Textarea.displayName = "Textarea";
