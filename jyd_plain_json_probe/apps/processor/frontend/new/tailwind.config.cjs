const path = require("path");

module.exports = {
  content: [path.join(__dirname, "*.html")],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Outfit", "Noto Sans SC", "sans-serif"],
      },
      colors: {
        brand: {
          deep: "#030712",
          dark: "#0b0f19",
          card: "rgba(17, 24, 39, 0.65)",
          primary: "#6366f1",
          secondary: "#a855f7",
          accent: "#06b6d4",
          success: "#10b981",
        },
      },
      backdropBlur: {
        xs: "2px",
      },
    },
  },
  plugins: [],
};
