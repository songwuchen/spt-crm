import type { Config } from 'tailwindcss'

const config: Config = {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
      colors: {
        primary: '#137fec',
        'bg-light': '#f8fafc',
      },
      boxShadow: {
        soft: '0 2px 15px -3px rgba(0,0,0,0.07), 0 10px 20px -2px rgba(0,0,0,0.04)',
        'primary-glow': '0 4px 14px 0 rgba(19, 127, 236, 0.25)',
      },
      borderRadius: {
        xl: '0.75rem',
      },
    },
  },
  plugins: [],
  corePlugins: {
    preflight: false,
  },
}

export default config
