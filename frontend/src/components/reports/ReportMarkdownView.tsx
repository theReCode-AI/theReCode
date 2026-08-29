import { renderSimpleMarkdown } from "@/utils/markdown";
import { sanitizeReportMarkdown } from "@/utils/reportMarkdown";

interface ReportMarkdownViewProps {
  markdown: string;
}

export function ReportMarkdownView({ markdown }: ReportMarkdownViewProps) {
  return (
    <article
      className="report-markdown"
      dangerouslySetInnerHTML={{ __html: renderSimpleMarkdown(sanitizeReportMarkdown(markdown)) }}
    />
  );
}
