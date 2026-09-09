export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // command-center palette: LIGHT professional base, restrained
        // semantic accents (green online / red critical / orange warning
        // / blue informational)
        cc: {
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
        },
      },
      fontFamily: {
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
    },
  },
  plugins: [],
};
