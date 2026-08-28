import { Link } from "react-router-dom";

interface SummaryCardProps {
  label: string;
  value: string | number;
  hint?: string;
  link?: string;
}

export function SummaryCard({ label, value, hint, link }: SummaryCardProps) {
  const content = (
    <>
      <span className="summary-label">{label}</span>
      <strong className="summary-value">{value}</strong>
      {hint ? <span className="summary-hint">{hint}</span> : null}
    </>
  );

  return (
    <article className="summary-card">
      {link ? (
        <Link to={link} className="summary-card-link">
          {content}
        </Link>
      ) : (
        content
      )}
    </article>
  );
}

interface RunSummaryGridProps {
  items: SummaryCardProps[];
}

export function RunSummaryGrid({ items }: RunSummaryGridProps) {
  return (
    <div className="summary-grid" data-testid="run-summary-grid">
      {items.map((item) => (
        <SummaryCard key={item.label} {...item} />
      ))}
    </div>
  );
}
