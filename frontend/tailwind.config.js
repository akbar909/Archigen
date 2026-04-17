/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,jsx,ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        ink: '#0f172a',
        mist: '#e2e8f0',
        accent: '#3b82f6',
        surface: '#0b1220',
      },
      boxShadow: {
        soft: '0 10px 30px rgba(15, 23, 42, 0.18)',
      },
    },
  },
  plugins: [],
}
