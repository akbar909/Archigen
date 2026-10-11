/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,jsx,ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        ink: '#171717',
        mist: '#e2e8f0',
        accent: '#10a37f',
        surface: '#0d0d0d',
      },
      boxShadow: {
        soft: '0 10px 30px rgba(0, 0, 0, 0.25)',
      },
    },
  },
  plugins: [],
}
