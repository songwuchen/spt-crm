import client from './client'
import type { ApiResponse, TokenResponse, UserInfo, LoginRequest } from './types'

export const authApi = {
  login: (data: LoginRequest) =>
    client.post<unknown, ApiResponse<TokenResponse>>('/api/v1/auth/login', data),
  dingtalkConfig: () =>
    client.get<unknown, ApiResponse<{ login_enabled: boolean; app_key: string; corp_id: string }>>('/api/v1/auth/dingtalk/config'),
  dingtalkCallback: (data: { code: string; redirect_uri: string; state?: string }) =>
    client.post<unknown, ApiResponse<TokenResponse>>('/api/v1/auth/dingtalk/callback', data),
  dingtalkJsapiLogin: (data: { auth_code: string; corp_id?: string }) =>
    client.post<unknown, ApiResponse<TokenResponse>>('/api/v1/auth/dingtalk/jsapi-login', data),
  refresh: (refresh_token: string) =>
    client.post<unknown, ApiResponse<TokenResponse>>('/api/v1/auth/refresh', { refresh_token }),
  me: () =>
    client.get<unknown, ApiResponse<UserInfo>>('/api/v1/auth/me'),
  updateProfile: (data: { real_name?: string; phone?: string; email?: string }) =>
    client.put<unknown, ApiResponse<{ real_name: string; phone: string; email: string }>>('/api/v1/auth/profile', data),
  // old_password 仅在 must_change_password 账号首次设密时可省略
  changePassword: (data: { old_password?: string; new_password: string }) =>
    client.post<unknown, ApiResponse<null>>('/api/v1/auth/change-password', data),
  sessions: () =>
    client.get<unknown, ApiResponse<SessionItem[]>>('/api/v1/auth/sessions'),
  revokeSession: (id: string) =>
    client.delete<unknown, ApiResponse<null>>(`/api/v1/auth/sessions/${id}`),
  revokeAllSessions: () =>
    client.post<unknown, ApiResponse<{ revoked: number }>>('/api/v1/auth/sessions/revoke-all'),
  totpStatus: () =>
    client.get<unknown, ApiResponse<{ enabled: boolean }>>('/api/v1/auth/totp/status'),
  totpSetup: () =>
    client.post<unknown, ApiResponse<{ secret: string; uri: string }>>('/api/v1/auth/totp/setup'),
  totpEnable: (code: string) =>
    client.post<unknown, ApiResponse<null>>('/api/v1/auth/totp/enable', { code }),
  totpDisable: (old_password: string) =>
    client.post<unknown, ApiResponse<null>>('/api/v1/auth/totp/disable', { old_password }),
}

export interface SessionItem {
  id: string; ip: string; device_type: string; user_agent: string
  last_active_at: string; created_at: string; is_current: boolean
}
