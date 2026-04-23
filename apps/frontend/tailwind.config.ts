import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      colors: {
        // open-swe-inspired palette: zinc neutrals + emerald accent
        bg: {
          DEFAULT: "rgb(250 250 250)",
          dark: "rgb(9 9 11)",
        },
        panel: {
          DEFAULT: "rgb(255 255 255)",
          dark: "rgb(24 24 27)",
        },
        border: {
          DEFAULT: "rgb(228 228 231)",
          dark: "rgb(39 39 42)",
        },
        fg: {
          DEFAULT: "rgb(24 24 27)",
          dark: "rgb(244 244 245)",
          muted: "rgb(113 113 122)",
        },
        accent: {
          DEFAULT: "rgb(22 163 74)",    // emerald-ish, open-swe style
          soft: "rgb(220 252 231)",
          fg: "rgb(255 255 255)",
        },
        warn: { DEFAULT: "rgb(234 179 8)", soft: "rgb(254 249 195)" },
        err:  { DEFAULT: "rgb(220 38 38)", soft: "rgb(254 226 226)" },
      },
      borderRadius: { xl: "0.75rem", "2xl": "1rem" },
      keyframes: {
        "fade-in":   { "0%": { opacity: "0" }, "100%": { opacity: "1" } },
        "slide-in":  { "0%": { transform: "translateY(4px)", opacity: "0" }, "100%": { transform: "translateY(0)", opacity: "1" } },
        "pulse-dot": { "0%,100%": { opacity: "1" }, "50%": { opacity: ".4" } },
      },
      animation: {
        "fade-in":  "fade-in 120ms ease-out",
        "slide-in": "slide-in 160ms ease-out",
        "pulse-dot":"pulse-dot 1.2s infinite",
      },
    },
  },
  plugins: [],
};
export default config;
