/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        kisan: {
          50: '#f2fbf5', 100: '#e4f6e9', 200: '#c8ecd3', 300: '#9dd9b1',
          400: '#68bf88', 500: '#3aa96a', 600: '#218a50', 700: '#176d40',
          800: '#125634', 900: '#0b3e27'
        },
        ink: '#10231a'
      },
      boxShadow: {
        soft: '0 12px 35px rgba(16, 55, 34, .08)',
        lift: '0 20px 55px rgba(16, 55, 34, .14)'
      },
      animation: {
        'pulse-soft': 'pulseSoft 2s ease-in-out infinite',
        'float-in': 'floatIn .45s ease-out both'
      },
      keyframes: {
        pulseSoft: { '0%,100%': { opacity: '.55' }, '50%': { opacity: '1' } },
        floatIn: { from: { opacity: '0', transform: 'translateY(8px)' }, to: { opacity: '1', transform: 'translateY(0)' } }
      }
    }
  },
  plugins: []
}
