"use client";

import { useCallback, useEffect, useRef, useState } from "react";

interface AsyncState<T> {
  data: T | null;
  error: unknown;
  isLoading: boolean;
}

/**
 * Runs `asyncFn` on mount and whenever its identity changes, and exposes
 * `refetch`. Wrap the function in `useCallback` with the inputs it depends
 * on (a filter, an id) — a new function means "fetch again".
 *
 * Only the LATEST call may update state, so a slow earlier response can't
 * overwrite a newer one. Existing data is kept while refetching and after a
 * failed refetch, so a table doesn't blank out on a hiccup.
 */
export function useAsync<T>(asyncFn: () => Promise<T>) {
  const [state, setState] = useState<AsyncState<T>>({ data: null, error: null, isLoading: true });
  const latest = useRef(0);

  const execute = useCallback(() => {
    const call = ++latest.current;
    setState((previous) => ({ ...previous, isLoading: true, error: null }));
    asyncFn().then(
      (data) => {
        if (latest.current === call) setState({ data, error: null, isLoading: false });
      },
      (error: unknown) => {
        if (latest.current === call) setState((previous) => ({ data: previous.data, error, isLoading: false }));
      },
    );
  }, [asyncFn]);

  // Starting a fetch from an effect is exactly what an effect is for here;
  // the rule below targets derived state, which this isn't.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    execute();
    return () => {
      // `latest` is a call counter, not a DOM node: bumping it at cleanup time is the point,
      // so anything still in flight after unmount or a change of inputs is ignored.
      // eslint-disable-next-line react-hooks/exhaustive-deps
      latest.current++;
    };
  }, [execute]);

  /** Replace the data locally — e.g. with the server's answer to a mutation — without refetching. */
  const mutate = useCallback((update: (current: T | null) => T | null) => {
    setState((previous) => ({ ...previous, data: update(previous.data) }));
  }, []);

  return { ...state, refetch: execute, mutate };
}
