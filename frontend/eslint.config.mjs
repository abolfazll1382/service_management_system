import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

/**
 * Layer boundaries. The app is built in layers, each allowed to depend only
 * on the ones below it:
 *
 *   types → lib → providers/hooks → components/ui → components/domain
 *         → components/layout → features → app
 *
 * The one hard rule that makes the mock backend replaceable: UI code reaches
 * data ONLY through `@/lib/api`. Only `lib/api` may import `lib/mock-server`,
 * and only `lib/mock-server` may touch the persisted "database" in `lib/store`.
 * Swapping in a real backend then means rewriting `lib/api/*` and nothing else.
 */
const forbid = (group, message) => ({ group, message });

const NO_BACKEND_INTERNALS = forbid(
  ["@/lib/mock-server", "@/lib/mock-server/*", "@/lib/store", "@/lib/store/*", "@/lib/api/mockClient"],
  "UI code must not reach into the mock backend. Call it through `@/lib/api`, which is the seam a real backend replaces.",
);

const UI_FOLDERS = ["@/components/*", "@/features/*", "@/providers/*", "@/hooks/*", "@/app/*"];

const restrict = (...patterns) => ["error", { patterns }];

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    rules: {
      // `_name` marks a deliberately unused binding; a rest sibling is how a field is omitted from a copy.
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_", caughtErrorsIgnorePattern: "^_", ignoreRestSiblings: true },
      ],
    },
  },
  {
    files: ["src/components/**", "src/features/**", "src/providers/**", "src/hooks/**", "src/app/**"],
    rules: { "no-restricted-imports": restrict(NO_BACKEND_INTERNALS) },
  },
  {
    files: ["src/lib/**", "src/types/**"],
    rules: {
      "no-restricted-imports": restrict(forbid(UI_FOLDERS, "`lib` and `types` sit below the UI and must not import from it.")),
    },
  },
  {
    files: ["src/providers/**", "src/hooks/**"],
    rules: {
      "no-restricted-imports": restrict(
        NO_BACKEND_INTERNALS,
        forbid(["@/components/*", "@/features/*", "@/app/*"], "Providers and hooks sit below components and must not import from them."),
      ),
    },
  },
  {
    files: ["src/components/ui/**"],
    rules: {
      "no-restricted-imports": restrict(
        NO_BACKEND_INTERNALS,
        forbid(
          ["@/components/domain/*", "@/components/layout/*", "@/features/*", "@/app/*"],
          "Base UI components are domain-free: they must not import domain, layout or feature code.",
        ),
      ),
    },
  },
  {
    files: ["src/components/domain/**"],
    rules: {
      "no-restricted-imports": restrict(
        NO_BACKEND_INTERNALS,
        forbid(["@/components/layout/*", "@/features/*", "@/app/*"], "Domain components must not import layout or feature code."),
      ),
    },
  },
  {
    files: ["src/components/layout/**"],
    rules: {
      "no-restricted-imports": restrict(NO_BACKEND_INTERNALS, forbid(["@/features/*", "@/app/*"], "Layout components must not import features or routes.")),
    },
  },
  {
    files: ["src/features/**"],
    rules: {
      "no-restricted-imports": restrict(NO_BACKEND_INTERNALS, forbid(["@/app/*"], "Features must not import from route files.")),
    },
  },
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);

export default eslintConfig;
