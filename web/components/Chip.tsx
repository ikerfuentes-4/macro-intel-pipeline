export default function Chip({
  children,
  tone = "slate",
}: {
  children: React.ReactNode;
  tone?: "slate" | "indigo";
}) {
  const cls =
    tone === "indigo"
      ? "bg-indigo-500/15 text-indigo-300 border-indigo-500/30"
      : "bg-slate-800 text-slate-300 border-slate-700";
  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-[11px] border mr-1 mb-1 ${cls}`}>
      {children}
    </span>
  );
}
