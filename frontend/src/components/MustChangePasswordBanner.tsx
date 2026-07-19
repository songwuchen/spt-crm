import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/useAuthStore'

/**
 * 提示「你的账号还在用系统代设的默认密码」。
 *
 * 钉钉组织同步代建的账号，密码是全租户共享的默认值、本人从未设过，
 * 光有服务端的免原密码通道不够——不主动提示的话用户根本不知道要去设。
 * 常驻不可关闭：这是个安全问题，设完密码标记自动消失，横幅随之隐藏。
 */
export default function MustChangePasswordBanner({ profilePath }: { profilePath: string }) {
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const userLoading = useAuthStore((s) => s.userLoading)

  if (userLoading || !user?.must_change_password) return null

  return (
    <div className="bg-amber-50 border-b border-amber-200 px-4 py-2 flex items-center gap-3 text-sm">
      <span className="flex-1 text-amber-800 font-medium">
        你的账号仍在使用系统代设的默认密码，请尽快设置自己的密码。
      </span>
      <button
        onClick={() => navigate(profilePath)}
        className="shrink-0 px-3 py-1 rounded-md bg-amber-600 text-white font-bold hover:bg-amber-700 active:opacity-80"
      >
        去设置
      </button>
    </div>
  )
}
