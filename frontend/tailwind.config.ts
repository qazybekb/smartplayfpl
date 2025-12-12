import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // FPL-inspired colors
        fpl: {
          purple: "#37003c",
          green: "#00ff87",
          cyan: "#04f5ff",
        },
        // Position colors
        position: {
          gkp: "#f97316", // orange
          def: "#22c55e", // green
          mid: "#3b82f6", // blue
          fwd: "#ef4444", // red
        },
        // FDR colors
        fdr: {
          1: "#147d46", // Very easy - green
          2: "#00ff87", // Easy - light green
          3: "#e7e7e7", // Medium - gray
          4: "#ff005a", // Hard - pink
          5: "#820024", // Very hard - dark red
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;

