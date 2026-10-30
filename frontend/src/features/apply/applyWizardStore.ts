import { create } from "zustand";

export const APPLY_STEPS = ["applicant", "details", "review"] as const;
export type ApplyStep = (typeof APPLY_STEPS)[number];

interface ApplyWizardState {
  /** Index of the step being shown. */
  step: number;
  /** The furthest step reached; earlier ones can be revisited from the stepper, later ones can't be skipped to. */
  furthest: number;
  next: () => void;
  back: () => void;
  goTo: (index: number) => void;
  reset: () => void;
}

const INITIAL = { step: 0, furthest: 0 };
const LAST = APPLY_STEPS.length - 1;

/**
 * Only the NAVIGATION state lives here — which step, how far the person has
 * got — because the stepper, the footer buttons and the step bodies all need
 * it. The form's values live in react-hook-form, which already tracks them.
 */
export const useApplyWizardStore = create<ApplyWizardState>((set) => ({
  ...INITIAL,
  next: () =>
    set(({ step, furthest }) => {
      const to = Math.min(step + 1, LAST);
      return { step: to, furthest: Math.max(furthest, to) };
    }),
  back: () => set(({ step }) => ({ step: Math.max(step - 1, 0) })),
  goTo: (index) => set(({ furthest }) => (index >= 0 && index <= furthest ? { step: index } : {})),
  reset: () => set(INITIAL),
}));
