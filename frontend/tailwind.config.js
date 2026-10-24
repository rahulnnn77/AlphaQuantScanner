/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        dark: {
          bg: '#0B0F19',
          surface: '#111827',
          card: '#161F30',
          border: '#1F2937',
          muted: '#9CA3AF',
        },
        brand: {
          primary: '#6366F1',
          primaryHover: '#4F46E5',
        },
        bullish: '#10B981',
        bearish: '#EF4444',
      },
      fontFamily: {
        sans: ['-apple-system', 'BlinkMacSystemFont', '"SF Pro Display"', '"SF Pro Text"', '"SF Pro"', '"Helvetica Neue"', 'Helvetica', 'Arial', 'sans-serif'],
        mono: ['"SF Mono"', 'SFMono-Regular', 'ui-monospace', 'Menlo', 'Monaco', 'Consolas', 'monospace'],
      }
    },
  },
  plugins: [],
}
