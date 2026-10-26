import type { TransactionFilters } from "@/lib/transactions";

interface Props {
  filters: TransactionFilters;
  onChange: (filters: TransactionFilters) => void;
}

export function TransactionFiltersBar({ filters, onChange }: Props) {
  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-3 text-sm">
      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={filters.fraudOnly}
          onChange={(e) => onChange({ ...filters, fraudOnly: e.target.checked })}
          className="size-4 accent-accent"
        />
        Fraud only
      </label>
      <label className="flex items-center gap-2">
        Minimum score
        <input
          type="range"
          min={0}
          max={1}
          step={0.05}
          value={filters.minScore}
          onChange={(e) => onChange({ ...filters, minScore: Number(e.target.value) })}
          className="w-28 accent-accent"
        />
        <output className="w-9 text-ink">{filters.minScore.toFixed(2)}</output>
      </label>
      <label className="flex items-center gap-2">
        <span className="sr-only">Search by transaction id</span>
        <input
          type="search"
          placeholder="Search by transaction id"
          value={filters.query}
          onChange={(e) => onChange({ ...filters, query: e.target.value })}
          className="w-64 rounded-md border border-line bg-surface px-3 py-1.5"
        />
      </label>
    </div>
  );
}
