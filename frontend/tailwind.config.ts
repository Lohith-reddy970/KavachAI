import type { Config } from "tailwindcss";

const color = (token: string) => `rgb(var(--${token}) / <alpha-value>)`;

/**
 * KAVACH AI — field-manual palette: drafting paper, machine ink, and safety oxide.
 */
const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        canvas: color("canvas"),
        surface: {
          DEFAULT: color("surface"),
          raised: color("surface-raised"),
          inset: color("surface-inset"),
        },
        line: {
          DEFAULT: color("line"),
          strong: color("line-strong"),
        },
        ink: {
          DEFAULT: color("ink"),
          muted: color("ink-muted"),
          faint: color("ink-faint"),
        },
        signal: {
          DEFAULT: color("signal"),
          dim: color("signal-dim"),
          glow: color("signal-glow"),
        },
        caution: color("caution"),
        danger: color("danger"),
        verified: color("verified"),
        info: color("info"),
        rail: {
          DEFAULT: color("rail"),
          raised: color("rail-raised"),
          line: color("rail-line"),
          ink: color("rail-ink"),
          muted: color("rail-muted"),
          faint: color("rail-faint"),
          accent: color("rail-accent"),
          meter: color("rail-meter"),
        },
      },
      fontFamily: {
        display: ["var(--font-display)", "sans-serif"],
        sans: ["var(--font-sans)", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      fontSize: {
        "2xs": ["0.6875rem", { lineHeight: "1rem", letterSpacing: "0.04em" }],
      },
      boxShadow: {
        panel:
          "0 1px 0 0 rgba(255,255,255,0.78) inset, 0 14px 30px -20px rgb(var(--ink) / 0.32)",
        glow: "0 0 0 1px rgb(var(--signal) / 0.45), 0 7px 22px -12px rgb(var(--signal) / 0.55)",
      },
      backgroundImage: {
        grid: "linear-gradient(rgb(var(--ink) / 0.09) 1px, transparent 1px), linear-gradient(90deg, rgb(var(--ink) / 0.075) 1px, transparent 1px)",
      },
      keyframes: {
        pulseline: {
          "0%": { transform: "translateX(-100%)" },
          "100%": { transform: "translateX(400%)" },
        },
        blip: {
          "0%,100%": { opacity: "1" },
          "50%": { opacity: "0.35" },
        },
        flow: {
          "0%": { strokeDashoffset: "24" },
          "100%": { strokeDashoffset: "0" },
        },
        sweep: {
          "0%": { transform: "translateY(-100%)" },
          "100%": { transform: "translateY(100%)" },
        },
        fadein: {
          "0%": { opacity: "0", transform: "translateY(4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        pageIn: {
          "0%": { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        pulseline: "pulseline 2.2s cubic-bezier(0.4,0,0.2,1) infinite",
        blip: "blip 1.6s ease-in-out infinite",
        flow: "flow 1s linear infinite",
        sweep: "sweep 3.5s linear infinite",
        fadein: "fadein 0.35s ease-out both",
        pageIn: "pageIn 0.55s cubic-bezier(0.2,0.75,0.25,1) both",
      },
    },
  },
  plugins: [],
};

export default config;
