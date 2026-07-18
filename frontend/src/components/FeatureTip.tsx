import { useState } from 'react'
import { CloseOutlined } from '@ant-design/icons'

import Icon from '@/components/Icon'
interface FeatureTipProps {
  id: string
  title: string
  content: string
  icon?: string
}

const STORAGE_PREFIX = 'spt_tip_dismissed_'

/**
 * Inline feature tip/hint bubble. Shows once per feature, dismissed permanently.
 */
export default function FeatureTip({ id, title, content, icon = 'lightbulb' }: FeatureTipProps) {
  const storageKey = `${STORAGE_PREFIX}${id}`
  const [visible, setVisible] = useState(() => !localStorage.getItem(storageKey))

  if (!visible) return null

  const dismiss = () => {
    localStorage.setItem(storageKey, '1')
    setVisible(false)
  }

  return (
    <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg px-3 py-2 flex items-start gap-2 mb-3 animate-fadeIn">
      <Icon name={icon} className="text-blue-500 mt-0.5" style={{ fontSize: 16 }} />
      <div className="flex-1 min-w-0">
        <div className="text-sm font-bold text-blue-700">{title}</div>
        <div className="text-sm text-blue-600 mt-0.5">{content}</div>
      </div>
      <CloseOutlined className="text-blue-400 hover:text-blue-600 cursor-pointer text-sm mt-0.5 shrink-0" onClick={dismiss} />
    </div>
  )
}
