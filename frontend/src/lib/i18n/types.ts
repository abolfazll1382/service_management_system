import type { en } from "./dictionaries/en";

/** Every leaf string widened, so `fa` must supply the same keys with any text. */
type Widen<T> = T extends string ? string : { readonly [K in keyof T]: Widen<T[K]> };
export type Dictionary = Widen<typeof en>;

type Join<Prefix extends string, Key extends string> = Prefix extends "" ? Key : `${Prefix}.${Key}`;
type LeafKeys<T, Prefix extends string = ""> = T extends string
  ? Prefix
  : { [K in keyof T & string]: LeafKeys<T[K], Join<Prefix, K>> }[keyof T & string];

/**
 * Every valid dotted key, e.g. "common.actions.save". `t("common.actoins.save")`
 * is a compile error, and `t(`common.status.${status}`)` type-checks only when
 * every possible `status` has a translation.
 */
export type TranslationKey = LeafKeys<Dictionary>;

export type TranslationParams = Readonly<Record<string, string | number>>;
export type Translate = (key: TranslationKey, params?: TranslationParams) => string;
