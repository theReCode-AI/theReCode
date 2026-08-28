export type DiffLineKind = "add" | "remove" | "meta" | "context";

export interface DiffLine {
  kind: DiffLineKind;
  text: string;
}

export function parseUnifiedDiff(content: string): DiffLine[] {
  return content.split("\n").map((line) => {
    if (line.startsWith("+++") || line.startsWith("---") || line.startsWith("@@")) {
      return { kind: "meta", text: line };
    }
    if (line.startsWith("+")) {
      return { kind: "add", text: line };
    }
    if (line.startsWith("-")) {
      return { kind: "remove", text: line };
    }
    return { kind: "context", text: line };
  });
}
