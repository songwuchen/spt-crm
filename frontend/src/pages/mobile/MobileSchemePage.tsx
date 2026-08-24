// 移动端 → 方案管理：跳转到拆分后的三个独立表单模块。
import { useNavigate } from 'react-router-dom'
import MobileIcon from '@/components/MobileIcon'
import { usePageTitle } from '@/hooks/usePageTitle'
import { lowcodeApi } from '@/api/lowcode'
import { message } from 'antd'

const ENTRIES = [
  {
    key: 'drawing_requisition',
    title: '合同图纸领用',
    desc: '有合同号时发起图纸领用',
    icon: 'draft',
  },
  {
    key: 'install_drawing_notice',
    title: '安装图设计通知',
    desc: '无合同号 / 前期投标方案',
    icon: 'architecture',
  },
  {
    key: 'presale_service_notice',
    title: '售前服务通知',
    desc: '售前现场服务安排',
    icon: 'engineering',
  },
] as const

export default function MobileSchemePage() {
  usePageTitle('方案管理')
  const nav = useNavigate()

  const openModule = async (code: string) => {
    try {
      const res = await lowcodeApi.ensureBuiltin(code)
      nav(`/m/lowcode/forms/${res.data.id}/fill?code=${encodeURIComponent(code)}&returnTo=${encodeURIComponent('/m/solutions')}`)
    } catch {
      message.error('加载表单失败')
    }
  }

  return (
    <div style={{ paddingBottom: 'calc(env(safe-area-inset-bottom) + 80px)' }}>
      <div className="flex items-center justify-between mb-4">
        <button onClick={() => nav(-1)} className="flex items-center text-primary bg-transparent border-0 cursor-pointer p-0">
          <MobileIcon name="arrow_back_ios" />
        </button>
        <h2 className="text-lg font-bold text-slate-900 flex-1 text-center">方案管理</h2>
        <span className="w-6" />
      </div>

      <div className="bg-primary/10 rounded-xl p-3 mb-4 text-sm text-primary/80">
        方案管理已拆分为独立表单，请选择业务类型进入。
      </div>

      <div className="flex flex-col gap-3">
        {ENTRIES.map((item) => (
          <button
            key={item.key}
            type="button"
            onClick={() => void openModule(item.key)}
            className="flex items-start gap-3 p-4 rounded-xl border border-slate-200 bg-white text-left cursor-pointer"
          >
            <MobileIcon name={item.icon} className="text-primary mt-0.5" style={{ fontSize: 22 }} />
            <div>
              <div className="font-bold text-slate-900">{item.title}</div>
              <div className="text-sm text-slate-500 mt-1">{item.desc}</div>
            </div>
            <MobileIcon name="chevron_right" className="text-slate-400 ml-auto self-center" style={{ fontSize: 20 }} />
          </button>
        ))}
      </div>
    </div>
  )
}
