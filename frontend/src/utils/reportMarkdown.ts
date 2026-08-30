import { formatFindingLocation } from "@/utils/findingLocation";

export function sanitizeReportMarkdown(markdown: string): string {
  return markdown.replace(
    /(\[[\w-]+\]\s+)([^\s]+?)(:\d+)/g,
    (_match, prefix: string, filePath: string, lineSuffix: string) => {
      const isAbsolutePath =
        filePath.startsWith("/") || /^[A-Za-z]:[\\/]/.test(filePath);
      if (!isAbsolutePath) {
        return `${prefix}${filePath}${lineSuffix}`;
      }

      const line = Number.parseInt(lineSuffix.slice(1), 10);
      return `${prefix}${formatFindingLocation(filePath, line)}`;
    },
  );
}
