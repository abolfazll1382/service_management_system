import { cn } from "@/lib/utils/cn";

interface SwitchProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  /** Accessible name — what this switch controls. */
  label: string;
  disabled?: boolean;
}

/** An on/off toggle. The knob slides toward the "end" edge when on, so it mirrors correctly in RTL. */
export function Switch({ checked, onChange, label, disabled }: SwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        "relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-tile-600",
        "disabled:cursor-not-allowed disabled:opacity-50",
        checked ? "bg-tile-700" : "bg-ink-300",
      )}
    >
      <span
        aria-hidden="true"
        className={cn(
          "absolute top-0.5 h-5 w-5 rounded-full bg-white transition-all",
          checked ? "end-0.5" : "start-0.5",
        )}
      />
    </button>
  );
}
