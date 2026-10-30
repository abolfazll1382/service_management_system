"use client";

import { Check } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { useFormat, useT } from "@/providers/LocaleProvider";

interface WizardStepperProps {
  labels: readonly string[];
  current: number;
  furthest: number;
  onStepClick: (index: number) => void;
}

/**
 * Flex rows reverse by themselves under dir="rtl" (step 1 sits on the right),
 * so nothing here is direction-specific except that numbers are rendered in
 * the active script.
 */
export function WizardStepper({ labels, current, furthest, onStepClick }: WizardStepperProps) {
  const t = useT();
  const format = useFormat();
  return (
    <nav aria-label={t("request.wizard.progress")}>
      <ol className="flex items-start">
        {labels.map((label, index) => {
          const done = index < current;
          const active = index === current;
          const reachable = index <= furthest;
          return (
            <li key={label} className={cn("flex items-start", index < labels.length - 1 && "flex-1")}>
              <button
                type="button"
                onClick={() => onStepClick(index)}
                disabled={!reachable}
                aria-current={active ? "step" : undefined}
                className="flex flex-col items-center gap-2 disabled:cursor-not-allowed focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-tile-600"
              >
                <span
                  className={cn(
                    "flex h-9 w-9 items-center justify-center rounded-full border-2 text-sm font-bold transition-colors",
                    done && "border-tile-700 bg-tile-700 text-white",
                    active && "border-tile-700 bg-white text-tile-700",
                    !done && !active && "border-ink-200 bg-white text-ink-400",
                  )}
                >
                  {done ? <Check className="h-4 w-4" aria-hidden="true" /> : format.number(index + 1)}
                </span>
                <span className={cn("max-w-24 text-center text-xs font-medium", active ? "text-ink-950" : "text-ink-500")}>{label}</span>
              </button>
              {index < labels.length - 1 && (
                <span aria-hidden="true" className={cn("mx-2 mt-[1.1rem] h-0.5 flex-1 rounded", done ? "bg-tile-700" : "bg-ink-200")} />
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
