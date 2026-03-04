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
}
