/** 合同登记分区标题：居中 + 两侧分割线（对齐简道云 separator 观感） */
export default function ContractSectionTitle({ title, className = '' }: { title: string; className?: string }) {
  return (
    <div className={`flex items-center gap-3 mb-3 ${className}`}>
      <div className="flex-1 h-px bg-slate-200" />
      <span className="text-[13px] font-bold text-slate-700 shrink-0 tracking-wide">{title}</span>
      <div className="flex-1 h-px bg-slate-200" />
    </div>
  )
}
