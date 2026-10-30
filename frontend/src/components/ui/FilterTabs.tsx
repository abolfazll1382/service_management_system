import { cn } from "@/lib/utils/cn";

export interface FilterOption<Value extends string> {
  value: Value;
  label: string;
  count?: number;
}

interface FilterTabsProps<Value extends string> {
  label: string;
  options: readonly FilterOption<Value>[];
  value: Value;
  onChange: (value: Value) => void;
  formatCount?: (count: number) => string;
}

/** A row of toggle buttons for narrowing a list (e.g. by status), with live counts. */
export function FilterTabs<Value extends string>({ label, options, value, onChange, formatCount }: FilterTabsProps<Value>) {
  return (
    <div role="group" aria-label={label} className="-mx-1 flex gap-1.5 overflow-x-auto px-1 pb-1">
      {options.map((option) => {
        const active = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(option.value)}
            className={cn(
              "inline-flex shrink-0 items-center gap-2 rounded-full border px-3.5 py-1.5 text-sm font-medium transition-colors",
              "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-tile-600",
              active ? "border-ink-900 bg-ink-900 text-white" : "border-ink-200 bg-white text-ink-700 hover:border-ink-300 hover:bg-ink-50",
            )}
          >
            {option.label}
            {option.count !== undefined && (
              <span className={cn("rounded-full px-1.5 text-xs tabular-nums", active ? "bg-white/20 text-white" : "bg-ink-100 text-ink-600")}>
                {formatCount ? formatCount(option.count) : option.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
