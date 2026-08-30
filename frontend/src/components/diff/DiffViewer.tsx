import { parseUnifiedDiff } from "@/utils/diff";

interface DiffViewerProps {
  content: string;
  title?: string;
}

export function DiffViewer({ content, title }: DiffViewerProps) {
  const lines = parseUnifiedDiff(content);

  return (
    <section className="diff-viewer" data-testid="diff-viewer">
      {title ? <h3>{title}</h3> : null}
      <pre className="diff-content">
        {lines.map((line, index) => (
          <code key={`${index}-${line.text}`} className={`diff-line diff-${line.kind}`}>
            {line.text || " "}
          </code>
        ))}
      </pre>
    </section>
  );
}
