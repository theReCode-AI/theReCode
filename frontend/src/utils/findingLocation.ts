export function formatFindingLocation(
  file: string | null | undefined,
  lineStart?: number | null,
): string {
  if (!file) {
    return "—";
  }

  const fileName = file.replace(/\\/g, "/").split("/").pop() ?? file;
  return lineStart ? `${fileName}:${lineStart}` : fileName;
}
