export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Command-center palette: dark-first, restrained semantic accents.
        // Light values are the fallback; .dark switches the whole surface.
        cc: {
          // Light (default)
          bg: '#F6F7F9',
          panel: '#FFFFFF',
          panel2: '#F2F4F6',
          line: '#E3E7EB',
          text: '#101418',
          dim: '#5C6672',
          accent: '#16A34A',
          red: '#DC2626',
          amber: '#D97706',
          blue: '#2563EB',
          // Dark (via .dark class)
          'bg-dark': '#0B0F14',
          'panel-dark': '#11171E',
          'panel2-dark': '#161D26',
          'line-dark': '#1E2834',
          'text-dark': '#E8EBF0',
          'dim-dark': '#7A8796',
          'accent-dark': '#22C55E',
          'red-dark': '#EF4444',
          'amber-dark': '#F59E0B',
          'blue-dark': '#3B82F6',
        },
      },
      fontFamily: {
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Consolas', 'monospace'],
        sans: ['ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
      },
      fontSize: {
        'xs': ['10px', { lineHeight: '14px', letterSpacing: '0.08em' }],
        'sm': ['11px', { lineHeight: '16px', letterSpacing: '0.04em' }],
        'base': ['13px', { lineHeight: '20px' }],
        'lg': ['15px', { lineHeight: '24px' }],
        'xl': ['18px', { lineHeight: '28px', letterSpacing: '-0.01em', fontWeight: '500' }],
        '2xl': ['22px', { lineHeight: '32px', letterSpacing: '-0.02em', fontWeight: '600' }],
        '3xl': ['32px', { lineHeight: '40px', letterSpacing: '-0.03em', fontWeight: '600' }],
        'mono-xs': ['9px', { lineHeight: '13px', letterSpacing: '0.1em', fontWeight: '500' }],
        'mono-sm': ['10px', { lineHeight: '14px', letterSpacing: '0.08em', fontWeight: '500' }],
        'mono-base': ['11px', { lineHeight: '16px', letterSpacing: '0.04em', fontWeight: '500' }],
        'mono-lg': ['13px', { lineHeight: '20px', fontWeight: '600' }],
        'mono-xl': ['18px', { lineHeight: '26px', letterSpacing: '-0.01em', fontWeight: '700' }],
      },
      spacing: {
        '0': '0',
        '1': '4px',
        '2': '8px',
        '3': '12px',
        '4': '16px',
        '5': '20px',
        '6': '24px',
        '8': '32px',
        '10': '40px',
        '12': '48px',
      },
      borderRadius: {
        'sm': '4px',
        'md': '6px',
        'lg': '8px',
        'xl': '12px',
        'full': '9999px',
      },
      boxShadow: {
        'sm': '0 1px 2px 0 rgb(0 0 0 / 0.05)',
        'DEFAULT': '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)',
        'md': '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)',
        'lg': '0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)',
      },
      transitionDuration: {
        'instant': '0ms',
        'fast': '100ms',
        'base': '160ms',
        'slow': '240ms',
        'slower': '320ms',
      },
      transitionTimingFunction: {
        'standard': 'cubic-bezier(0.4, 0, 0.2, 1)',
        'emphasized': 'cubic-bezier(0.2, 0, 0, 1)',
        'decelerate': 'cubic-bezier(0, 0, 0.2, 1)',
      },
      animation: {
        'pulse-subtle': 'pulse-subtle 1.5s ease-in-out infinite',
        'fade-in': 'fade-in 160ms ease-out',
        'slide-up': 'slide-up 160ms ease-out',
        'slide-down': 'slide-down 160ms ease-out',
      },
      keyframes: {
        'pulse-subtle': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.6' },
        },
        'fade-in': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        'slide-up': {
          '0%': { opacity: '0', transform: 'translateY(4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'slide-down': {
          '0%': { opacity: '0', transform: 'translateY(-4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
}