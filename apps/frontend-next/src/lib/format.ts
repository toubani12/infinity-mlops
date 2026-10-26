const amountFormat = new Intl.NumberFormat("en-IE", { style: "currency", currency: "EUR" });
const timeFormat = new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
const dateTimeFormat = new Intl.DateTimeFormat("en-GB", {
  day: "2-digit",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
});

export function formatAmount(amount: number): string {
  return amountFormat.format(amount);
}

export function formatTime(iso: string, now: Date = new Date()): string {
  const date = new Date(iso);
  return date.toDateString() === now.toDateString() ? timeFormat.format(date) : dateTimeFormat.format(date);
}

export function formatWhen(iso: string, now: Date = new Date()): string {
  const sameDay = new Date(iso).toDateString() === now.toDateString();
  return `${sameDay ? "at" : "on"} ${formatTime(iso, now)}`;
}

export function formatScore(score: number): string {
  return score.toFixed(3);
}

export function shortId(id: string): string {
  return id.slice(0, 8);
}

export type RiskBand = "high" | "elevated" | "low";

export function riskBand(score: number, threshold = 0.5): RiskBand {
  if (score >= threshold) {
    return "high";
  }
  return score >= threshold / 2 ? "elevated" : "low";
}
