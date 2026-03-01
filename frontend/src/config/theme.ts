import type { ThemeConfig } from 'antd'

export const theme: ThemeConfig = {
  token: {
    colorPrimary: '#137fec',
    borderRadius: 8,
    fontFamily: "'Inter', system-ui, -apple-system, sans-serif",
    colorBgLayout: '#f8fafc',
    colorBorderSecondary: '#e2e8f0',
  },
  components: {
    Button: {
      fontWeight: 600,
      controlHeight: 36,
      controlHeightLG: 40,
      controlHeightSM: 28,
      borderRadius: 8,
      borderRadiusLG: 8,
      borderRadiusSM: 6,
      defaultBorderColor: '#e2e8f0',
      defaultColor: '#334155',
      defaultBg: '#ffffff',
      defaultShadow: '0 1px 2px 0 rgba(0,0,0,0.05)',
      primaryShadow: '0 1px 2px 0 rgba(0,0,0,0.05)',
      dangerShadow: '0 1px 2px 0 rgba(0,0,0,0.05)',
      paddingInline: 16,
      paddingInlineLG: 20,
      paddingInlineSM: 12,
    },
    Table: {
      headerBg: '#f1f5f9',
      headerColor: '#64748b',
      headerSplitColor: '#e2e8f0',
      rowHoverBg: '#f8fafc',
      borderColor: '#f1f5f9',
    },
    Card: {
      borderRadiusLG: 12,
    },
    Menu: {
      darkItemBg: '#0f172a',
      darkSubMenuItemBg: '#0f172a',
      darkItemSelectedBg: '#137fec',
    },
    Input: {
      controlHeight: 36,
      borderRadius: 8,
    },
    Select: {
      controlHeight: 36,
      borderRadius: 8,
    },
  },
}
