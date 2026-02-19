/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx}",
    "./components/**/*.{js,ts,jsx,tsx}"
  ],
  theme: {
    extend: {
      colors: {
        primaryBlue: "#3FD1FF",
        primaryRed: "#FF4655",
        bgDark: "#0B0E14",
        cardBg: "rgba(255,255,255,0.03)",
        textMain: "#EAEAEA",
        textDim: "#9AA0A6"
      },
      fontFamily: {
        orbitron: ["Orbitron", "system-ui", "sans-serif"],
        inter: ["Inter", "system-ui", "sans-serif"]
      }
    }
  },
  plugins: []
}
