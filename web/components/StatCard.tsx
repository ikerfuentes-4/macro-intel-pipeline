export default function StatCard({
  title,
  value,
  sub,
  accent,
}: {
  title: string;
  value: string;
  sub: string;
  accent?: "emerald" | "rose" | "amber" | "slate";
}) {
  const color =
    accent === "emerald"
      ? "text-emerald-400"
      : accent === "rose"
        ? "text-rose-400"
        : accent === "amber"
          ? "text-amber-400"
          : "text-slate-100";

  return (
    <div className="border border-slate-800 rounded-lg p-4 bg-slate-900/50">
      <p className="text-xs text-slate-500">{title}</p>
      <p className={`text-2xl font-semibold mt-1 ${color}`}>{value}</p>
      <p className="text-xs text-slate-500 mt-1">{sub}</p>
    </div>
  );
}
