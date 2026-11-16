/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#0b0d12",
        panel: "#11141b",
        muted: "#828897",
        accent: "#a3e635",
      },
    },
  },
  plugins: [],
};
