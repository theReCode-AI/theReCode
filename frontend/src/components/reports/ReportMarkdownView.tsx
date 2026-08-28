import { renderSimpleMarkdown } from "@/utils/markdown";

interface ReportMarkdownViewProps {
  markdown: string;
}

export function ReportMarkdownView({ markdown }: ReportMarkdownViewProps) {
  return (
    <article
      className="report-markdown"
      dangerouslySetInnerHTML={{ __html: renderSimpleMarkdown(markdown) }}
    />
  );
}
