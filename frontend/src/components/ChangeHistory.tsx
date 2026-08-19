/** @deprecated 请优先使用 DataLog；本组件保留兼容旧 Tab 引用 */
import DataLog from '@/components/DataLog'

interface Props {
  resourceType: string
  resourceId: string
  fieldLabels?: Record<string, string>
}

export default function ChangeHistory({ resourceType, resourceId, fieldLabels }: Props) {
  return (
    <DataLog
      resourceType={resourceType}
      resourceId={resourceId}
      fieldLabels={fieldLabels}
    />
  )
}
