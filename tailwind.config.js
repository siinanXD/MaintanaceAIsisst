/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/templates/**/*.html",
    "./app/static/**/*.js"
  ],
  theme: {
    extend: {},
  },
  plugins: [require("daisyui")],
  daisyui: {
    themes: [
      {
        maintenance: {
          "primary": "#2563eb",
          "primary-content": "#ffffff",
          "secondary": "#0f766e",
          "secondary-content": "#ffffff",
          "accent": "#06b6d4",
          "accent-content": "#083344",
          "neutral": "#111827",
          "neutral-content": "#f8fafc",
          "base-100": "#ffffff",
          "base-200": "#f8fafc",
          "base-300": "#e2e8f0",
          "base-content": "#0f172a",
          "info": "#0284c7",
          "info-content": "#ffffff",
          "success": "#16a34a",
          "success-content": "#ffffff",
          "warning": "#facc15",
          "warning-content": "#422006",
          "error": "#dc2626",
          "error-content": "#ffffff"
        }
      }
    ]
  }
};
