import { cn } from "@/lib/utils/cn";

interface StatProps {
  label: string;
  value: string;
  /** Draws the eye to a number that is waiting on someone. */
  emphasis?: boolean;
}

export function Stat({ label, value, emphasis }: StatProps) {
  return (
    <div className={cn("rounded-xl border px-4 py-3", emphasis ? "border-saffron-300 bg-saffron-50" : "border-ink-200 bg-white")}>
      <dt className="text-xs font-medium text-ink-600">{label}</dt>
      <dd className="mt-0.5 text-2xl font-bold text-ink-950 tabular-nums">{value}</dd>
    </div>
  );
}
