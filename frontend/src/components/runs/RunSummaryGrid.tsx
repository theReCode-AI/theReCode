import { Link } from "react-router-dom";
import { Card } from "flowbite-react";

interface SummaryCardProps {
  label: string;
  value: string | number;
  hint?: string;
  link?: string;
}

export function SummaryCard({ label, value, hint, link }: SummaryCardProps) {
  const content = (
    <>
      <p className="text-sm text-gray-500">{label}</p>
      <p className="text-2xl font-bold text-gray-900">{value}</p>
      {hint ? <p className="text-sm text-gray-500">{hint}</p> : null}
    </>
  );

  return (
    <Card>
      {link ? (
        <Link to={link} className="block text-inherit no-underline hover:text-blue-600">
          {content}
        </Link>
      ) : (
        content
      )}
    </Card>
  );
}

interface RunSummaryGridProps {
  items: SummaryCardProps[];
}

export function RunSummaryGrid({ items }: RunSummaryGridProps) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4" data-testid="run-summary-grid">
      {items.map((item) => (
        <SummaryCard key={item.label} {...item} />
      ))}
    </div>
  );
}
