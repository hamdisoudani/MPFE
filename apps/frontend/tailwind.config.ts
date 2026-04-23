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
        // open-swe palette — zinc neutrals, near-black primary, no green accents
        bg: {
          DEFAULT: "rgb(250 250 250)",   // zinc-50
          dark: "rgb(9 9 11)",            // zinc-950
        },
        panel: {
          DEFAULT: "rgb(255 255 255)",
          dark: "rgb(24 24 27)",          // zinc-900
        },
        border: {
          DEFAULT: "rgb(228 228 231)",    // zinc-200
          dark: "rgb(39 39 42)",          // zinc-800
        },
        fg: {
          DEFAULT: "rgb(24 24 27)",       // zinc-900
          dark: "rgb(244 244 245)",       // zinc-100
          muted: "rgb(113 113 122)",      // zinc-500
        },
        // Primary = near-black (shadcn/open-swe style). Inverts in dark mode.
        accent: {
          DEFAULT: "rgb(24 24 27)",       // zinc-900
          soft: "rgb(244 244 245)",       // zinc-100
          fg: "rgb(250 250 250)",         // zinc-50
        },
        warn: { DEFAULT: "rgb(202 138 4)", soft: "rgb(254 249 195)" },  // amber-600
        err:  { DEFAULT: "rgb(185 28 28)", soft: "rgb(254 226 226)" },  // red-700
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
