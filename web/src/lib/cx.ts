/** Tiny class merge — shadcn-style cx without runtime deps. */
export function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}
