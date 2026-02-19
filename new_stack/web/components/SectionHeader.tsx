export default function SectionHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="mb-4">
      <h2 className="brand-title text-2xl font-semibold text-primaryBlue">{title}</h2>
      {subtitle ? <div className="text-sm text-textDim">{subtitle}</div> : null}
    </div>
  )
}
