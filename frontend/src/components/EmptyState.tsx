interface EmptyStateProps {
  icon?: string
  title?: string
  description?: string
}

export default function EmptyState({
  icon = 'inbox',
  title = '暂无数据',
  description,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-slate-400">
      <span className="material-symbols-outlined text-5xl mb-3">{icon}</span>
      <div className="text-sm font-medium">{title}</div>
      {description && <div className="text-sm mt-1">{description}</div>}
    </div>
  )
}
