import client from './client'

export const dashboardApi = {
  stats: () => client.get('/api/v1/dashboard/stats'),
  alerts: () => client.get('/api/v1/dashboard/alerts'),
  trends: () => client.get('/api/v1/dashboard/trends'),
  funnel: (params?: Record<string, unknown>) => client.get('/api/v1/dashboard/funnel', { params }),
  winLoss: (params?: Record<string, unknown>) => client.get('/api/v1/dashboard/win_loss', { params }),
  topCustomers: (params?: Record<string, unknown>) => client.get('/api/v1/dashboard/top_customers', { params }),
  paymentOverview: (params?: Record<string, unknown>) => client.get('/api/v1/dashboard/payment_overview', { params }),
  milestoneOverview: (params?: Record<string, unknown>) => client.get('/api/v1/dashboard/milestone_overview', { params }),
  monthlyRevenue: (params?: Record<string, unknown>) => client.get('/api/v1/dashboard/monthly_revenue', { params }),
  leaderboard: (params?: Record<string, unknown>) => client.get('/api/v1/dashboard/leaderboard', { params }),
  trend: (params?: Record<string, unknown>) => client.get('/api/v1/dashboard/trend', { params }),
  collection: (params?: Record<string, unknown>) => client.get('/api/v1/dashboard/collection', { params }),
  myOverview: () => client.get('/api/v1/dashboard/my_overview'),
  search: (params: Record<string, unknown>) => client.get('/api/v1/dashboard/search', { params }),

  // Sales targets
  listTargets: (params: Record<string, unknown>) => client.get('/api/v1/dashboard/targets', { params }),
  upsertTarget: (data: Record<string, unknown>) => client.post('/api/v1/dashboard/targets', data),
  deleteTarget: (id: string) => client.delete(`/api/v1/dashboard/targets/${id}`),
  targetAchievement: (params: Record<string, unknown>) => client.get('/api/v1/dashboard/target_achievement', { params }),
  customerRegionStats: () => client.get('/api/v1/dashboard/customer_region_stats'),
  calendarEvents: (params: Record<string, unknown>) => client.get('/api/v1/dashboard/calendar_events', { params }),
  contractExpiry: (params?: Record<string, unknown>) => client.get('/api/v1/dashboard/contract_expiry', { params }),
  exportExcelUrl: (params?: Record<string, string>) => {
    const qs = new URLSearchParams(params).toString()
    return `/api/v1/dashboard/export/excel${qs ? '?' + qs : ''}`
  },
  exportPdfUrl: (params?: Record<string, string>) => {
    const qs = new URLSearchParams(params).toString()
    return `/api/v1/dashboard/export/pdf${qs ? '?' + qs : ''}`
  },
}
