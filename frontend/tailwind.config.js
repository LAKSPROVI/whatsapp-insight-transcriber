/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Paleta futurista
        brand: {
          50: "#f0eeff",
          100: "#e3deff",
          200: "#cbc4fe",
          300: "#a99bfc",
          400: "#8b6ef8",
          500: "#6C63FF",
          600: "#5a4fe0",
          700: "#4a3fc0",
          800: "#3d349e",
          900: "#342c7e",
        },
        accent: {
          50: "#edfffe",
          100: "#c3fffd",
          200: "#88fff9",
          300: "#40fff4",
          400: "#00d4aa",
          500: "#00c19a",
          600: "#009d7e",
          700: "#007d67",
          800: "#006452",
          900: "#005344",
        },
        dark: {
          900: "#0a0a14",
          800: "#0f0f1e",
          700: "#141428",
          600: "#1a1a35",
          500: "#1e1e3f",
          400: "#252548",
          300: "#2d2d55",
        },
        surface: {
          50: "#f8f9ff",
          100: "#f0f1fc",
          200: "#e4e5f8",
          300: "#d1d2f0",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "sans-serif"],
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
      backgroundImage: {
        "gradient-radial": "radial-gradient(var(--tw-gradient-stops))",
        "gradient-conic": "conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))",
        "gradient-brand": "linear-gradient(135deg, #6C63FF 0%, #00d4aa 100%)",
        "gradient-dark": "linear-gradient(135deg, #0f0f1e 0%, #1a1a35 100%)",
        "glow-brand": "radial-gradient(ellipse at center, rgba(108,99,255,0.15) 0%, transparent 70%)",
      },
      boxShadow: {
        "brand": "0 0 20px rgba(108,99,255,0.3), 0 0 40px rgba(108,99,255,0.1)",
        "accent": "0 0 20px rgba(0,212,170,0.3), 0 0 40px rgba(0,212,170,0.1)",
        "card": "0 4px 24px rgba(0,0,0,0.4), 0 1px 2px rgba(0,0,0,0.3)",
        "glow": "0 0 30px rgba(108,99,255,0.4)",
        "inner-brand": "inset 0 0 20px rgba(108,99,255,0.1)",
      },
      animation: {
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "float": "float 6s ease-in-out infinite",
        "glow-pulse": "glow-pulse 2s ease-in-out infinite",
        "slide-up": "slideUp 0.3s ease-out",
        "slide-down": "slideDown 0.3s ease-out",
        "fade-in": "fadeIn 0.4s ease-out",
        "spin-slow": "spin 3s linear infinite",
        "bounce-subtle": "bounceSubtle 2s ease-in-out infinite",
        "shimmer": "shimmer 2s linear infinite",
        "scan": "scan 2s linear infinite",
      },
      keyframes: {
        float: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-10px)" },
        },
        "glow-pulse": {
          "0%, 100%": { boxShadow: "0 0 20px rgba(108,99,255,0.3)" },
          "50%": { boxShadow: "0 0 40px rgba(108,99,255,0.6)" },
        },
        slideUp: {
          from: { opacity: "0", transform: "translateY(10px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        slideDown: {
          from: { opacity: "0", transform: "translateY(-10px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        fadeIn: {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        bounceSubtle: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-4px)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        scan: {
          "0%": { transform: "translateY(-100%)" },
          "100%": { transform: "translateY(100%)" },
        },
      },
      backdropBlur: {
        xs: "2px",
      },
    },
  },
  plugins: [],
};
