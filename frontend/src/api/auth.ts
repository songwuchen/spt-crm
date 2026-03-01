import client from './client'
import type { ApiResponse, TokenResponse, UserInfo, LoginRequest } from './types'

export const authApi = {
  login: (data: LoginRequest) =>
    client.post<unknown, ApiResponse<TokenResponse>>('/api/v1/auth/login', data),
  refresh: (refresh_token: string) =>
    client.post<unknown, ApiResponse<TokenResponse>>('/api/v1/auth/refresh', { refresh_token }),
  me: () =>
    client.get<unknown, ApiResponse<UserInfo>>('/api/v1/auth/me'),
  updateProfile: (data: { real_name?: string; phone?: string; email?: string }) =>
    client.put<unknown, ApiResponse<{ real_name: string; phone: string; email: string }>>('/api/v1/auth/profile', data),
  changePassword: (data: { old_password: string; new_password: string }) =>
    client.post<unknown, ApiResponse<null>>('/api/v1/auth/change-password', data),
}
