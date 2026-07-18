import Icon from '@/components/Icon'

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
      <Icon name={icon} className="text-5xl mb-3" />
      <div className="text-sm font-medium">{title}</div>
      {description && <div className="text-sm mt-1">{description}</div>}
    </div>
  )
}
