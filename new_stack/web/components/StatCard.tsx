export default function StatCard({ label, value, accent }: { label: string; value: string | number; accent?: "blue" | "red" }) {
  const border = accent === "red" ? "border-primaryRed" : "border-primaryBlue"
  return (
    <div className={`card border-l-4 ${border} p-4`}>
      <div className="text-xs uppercase tracking-wide text-textDim">{label}</div>
      <div className="brand-title text-2xl mt-2">{value}</div>
    </div>
  )
}
