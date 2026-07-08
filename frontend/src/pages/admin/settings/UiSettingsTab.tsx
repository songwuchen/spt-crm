import { useEffect, useState } from 'react'
import { Input, Switch, Button, message, Spin } from 'antd'
import { settingsApi } from '@/api/settings'
import { menuGroups, PROTECTED_MENU_KEYS } from '@/config/menus'
import { useUiSettingsStore, type UiSettings } from '@/stores/useUiSettingsStore'
import { t } from '@/locales'

export default function UiSettingsTab() {
  const applyStore = useUiSettingsStore((s) => s.apply)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [systemName, setSystemName] = useState('')
  const [aliases, setAliases] = useState<Record<string, string>>({})
  const [hidden, setHidden] = useState<Set<string>>(new Set())

  const load = async () => {
    setLoading(true)
    try {
      const res = (await settingsApi.getUiSettings()) as unknown as { data?: UiSettings }
      const d = res.data || ({} as UiSettings)
      setSystemName(d.system_name || '')
      setAliases(d.menu_aliases || {})
      setHidden(new Set(d.hidden_menus || []))
    } catch {
      // 静默回退
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const setAlias = (key: string, val: string) =>
    setAliases((prev) => ({ ...prev, [key]: val }))

  const toggleHidden = (key: string, checked: boolean) =>
    setHidden((prev) => {
      const next = new Set(prev)
      if (checked) next.add(key)
      else next.delete(key)
      return next
    })

  const handleSave = async () => {
    setSaving(true)
    try {
      const payload = {
        system_name: systemName.trim() || null,
        menu_aliases: aliases,
        hidden_menus: Array.from(hidden),
      }
      const res = (await settingsApi.updateUiSettings(payload)) as unknown as { data?: UiSettings }
      const d = res.data || ({} as UiSettings)
      // 用后端清洗后的结果回填，并即时刷新全局状态（侧边栏/品牌名立即生效）
      setSystemName(d.system_name || '')
      setAliases(d.menu_aliases || {})
      setHidden(new Set(d.hidden_menus || []))
      applyStore(d)
      message.success('界面设置已保存')
    } catch {
      message.error('保存失败')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return <div className="flex justify-center py-16"><Spin /></div>
  }

  return (
    <div className="pb-6 max-w-3xl">
      <p className="text-sm text-slate-500 mb-4">
        自定义系统的显示名称，以及左侧导航菜单的别名与显示 / 隐藏。保存后立即对本租户所有用户生效。
      </p>

      {/* 系统显示名 */}
      <div className="bg-slate-50 rounded-xl p-4 border border-slate-200 mb-6">
        <label className="text-sm font-bold text-slate-700 mb-1 block">系统显示名</label>
        <p className="text-[12px] text-slate-400 mb-2">显示在左上角品牌区与浏览器标题；留空则使用默认「SPT-CRM」。</p>
        <Input
          value={systemName}
          maxLength={64}
          placeholder="SPT-CRM"
          className="!max-w-sm"
          onChange={(e) => setSystemName(e.target.value)}
        />
      </div>

      {/* 菜单别名与隐藏 */}
      <label className="text-sm font-bold text-slate-700 mb-2 block">菜单别名与隐藏</label>
      <div className="space-y-5">
        {menuGroups.map((group) => {
          const groupHidden = hidden.has(group.key)
          return (
            <div key={group.key} className="border border-slate-200 rounded-xl overflow-hidden">
              {/* 分组头 */}
              <div className="flex items-center gap-3 px-4 py-3 bg-slate-50 border-b border-slate-200">
                <span className="material-symbols-outlined text-slate-400 text-lg">folder</span>
                <Input
                  size="small"
                  value={aliases[group.key] ?? ''}
                  maxLength={64}
                  placeholder={`分组名（默认：${t(group.titleKey)}）`}
                  className="!max-w-[260px]"
                  onChange={(e) => setAlias(group.key, e.target.value)}
                />
                <div className="flex items-center gap-2 ml-auto">
                  <span className="text-[12px] text-slate-400">隐藏整组</span>
                  <Switch size="small" checked={groupHidden} onChange={(c) => toggleHidden(group.key, c)} />
                </div>
              </div>
              {/* 菜单项 */}
              <div className={groupHidden ? 'opacity-40 pointer-events-none' : ''}>
                {group.items.map((item) => {
                  const isProtected = PROTECTED_MENU_KEYS.includes(item.key)
                  return (
                    <div key={item.key} className="flex items-center gap-3 px-4 py-2 border-b border-slate-100 last:border-b-0">
                      <span className="material-symbols-outlined text-slate-300 text-base">{item.icon}</span>
                      <span className="text-sm text-slate-600 w-24 shrink-0">{t(item.labelKey)}</span>
                      <Input
                        size="small"
                        value={aliases[item.key] ?? ''}
                        maxLength={64}
                        placeholder={`别名（默认：${t(item.labelKey)}）`}
                        className="flex-1 !max-w-xs"
                        onChange={(e) => setAlias(item.key, e.target.value)}
                      />
                      <div className="flex items-center gap-2 ml-auto">
                        <span className="text-[12px] text-slate-400">隐藏</span>
                        <Switch
                          size="small"
                          disabled={isProtected}
                          checked={hidden.has(item.key)}
                          onChange={(c) => toggleHidden(item.key, c)}
                        />
                        {isProtected && <span className="text-[13px] text-amber-500 whitespace-nowrap">不可隐藏</span>}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>

      <div className="mt-6 flex gap-3">
        <Button type="primary" loading={saving} onClick={handleSave}>保存设置</Button>
        <Button onClick={load} disabled={saving}>重置</Button>
      </div>
    </div>
  )
}
