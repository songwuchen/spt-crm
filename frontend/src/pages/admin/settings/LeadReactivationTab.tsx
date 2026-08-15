import { useEffect, useState } from 'react'
import { Button, Input, InputNumber, Spin, Switch, TimePicker, message } from 'antd'
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons'
import dayjs, { type Dayjs } from 'dayjs'
import { settingsApi } from '@/api/settings'

type FormState = {
  enabled: boolean
  days: number
  scan_time: string
  skip_reporter_names: string[]
}

const DEFAULTS: FormState = {
  enabled: true,
  days: 180,
  scan_time: '09:00',
  skip_reporter_names: ['张贺'],
}

export default function LeadReactivationTab() {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState<FormState>(DEFAULTS)

  const load = async () => {
    setLoading(true)
    try {
      const res = await settingsApi.getLeadReactivation() as unknown as { data?: Partial<FormState> }
      const d = res.data || {}
      setForm({
        enabled: d.enabled !== false,
        days: typeof d.days === 'number' ? d.days : DEFAULTS.days,
        scan_time: d.scan_time || DEFAULTS.scan_time,
        skip_reporter_names: Array.isArray(d.skip_reporter_names) && d.skip_reporter_names.length
          ? d.skip_reporter_names.map(String)
          : [...DEFAULTS.skip_reporter_names],
      })
    } catch {
      message.error('加载线索重激活配置失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void load() }, [])

  const scanTimeValue: Dayjs | null = form.scan_time
    ? dayjs(form.scan_time, 'HH:mm')
    : null

  const setName = (i: number, val: string) => {
    setForm((prev) => ({
      ...prev,
      skip_reporter_names: prev.skip_reporter_names.map((n, idx) => (idx === i ? val : n)),
    }))
  }

  const handleSave = async () => {
    const names = form.skip_reporter_names.map((n) => n.trim()).filter(Boolean)
    if (!form.days || form.days < 1) {
      message.warning('请填写有效的重激活天数')
      return
    }
    setSaving(true)
    try {
      const res = await settingsApi.updateLeadReactivation({
        enabled: form.enabled,
        days: form.days,
        scan_time: form.scan_time,
        skip_reporter_names: names,
      }) as unknown as { data?: Partial<FormState> }
      const d = res.data || {}
      setForm({
        enabled: d.enabled !== false,
        days: typeof d.days === 'number' ? d.days : form.days,
        scan_time: d.scan_time || form.scan_time,
        skip_reporter_names: Array.isArray(d.skip_reporter_names)
          ? d.skip_reporter_names.map(String)
          : names,
      })
      message.success('线索重激活规则已保存')
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
    <div className="pb-6 max-w-lg">
      <p className="text-sm text-slate-500 mb-4">
        对齐简道云：按「申报时间」满设定天数的当天扫描触发重激活（非积压全扫）。
        通知申报人更新近况；暂缓/取消/落标结束本轮，其他结果经填表人后再次进入情报审批。
        保存后对本租户立即生效。
      </p>

      <div className="space-y-5">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm font-medium text-slate-700">启用自动重激活</div>
            <div className="text-xs text-slate-400 mt-0.5">关闭后不再扫描到期线索</div>
          </div>
          <Switch
            checked={form.enabled}
            onChange={(v) => setForm({ ...form, enabled: v })}
          />
        </div>

        <div>
          <label className="text-sm font-medium text-slate-700 mb-1 block">重激活周期（天）</label>
          <InputNumber
            className="w-full"
            min={1}
            max={3650}
            value={form.days}
            onChange={(v) => setForm({ ...form, days: v || 180 })}
            addonAfter="天"
            disabled={!form.enabled}
          />
          <p className="text-xs text-slate-400 mt-1">
            对齐简道云「申报时间」：满设定天数的当天扫描触发（非积压全扫），默认 180 天
          </p>
        </div>

        <div>
          <label className="text-sm font-medium text-slate-700 mb-1 block">每日扫描时刻（北京时间）</label>
          <TimePicker
            className="w-full"
            format="HH:mm"
            value={scanTimeValue}
            onChange={(t) => setForm({ ...form, scan_time: t ? t.format('HH:mm') : '09:00' })}
            disabled={!form.enabled}
            allowClear={false}
          />
          <p className="text-xs text-slate-400 mt-1">到达该时刻后由后台任务扫描一次（需 reminder_worker 运行）</p>
        </div>

        <div>
          <label className="text-sm font-medium text-slate-700 mb-2 block">跳过申报人待办（按姓名）</label>
          <p className="text-xs text-slate-400 mb-2">
            名单中的申报人：180 天重激活与「确认是否转商机」均不进本人待办，改派填表人（如张贺）
          </p>
          <div className="space-y-2">
            {form.skip_reporter_names.map((name, i) => (
              <div key={i} className="flex items-center gap-2">
                <Input
                  value={name}
                  placeholder="真实姓名"
                  disabled={!form.enabled}
                  onChange={(e) => setName(i, e.target.value)}
                />
                <Button
                  type="text"
                  danger
                  icon={<DeleteOutlined />}
                  disabled={!form.enabled}
                  onClick={() => setForm({
                    ...form,
                    skip_reporter_names: form.skip_reporter_names.filter((_, idx) => idx !== i),
                  })}
                />
              </div>
            ))}
            <Button
              type="dashed"
              size="small"
              icon={<PlusOutlined />}
              disabled={!form.enabled}
              onClick={() => setForm({
                ...form,
                skip_reporter_names: [...form.skip_reporter_names, ''],
              })}
              block
            >
              添加姓名
            </Button>
          </div>
        </div>

        <Button type="primary" loading={saving} onClick={() => void handleSave()}>
          保存规则
        </Button>
      </div>
    </div>
  )
}
