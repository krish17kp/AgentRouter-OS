/** @type {import('tailwindcss').Config} */
export default { content: ['./index.html', './src/**/*.{ts,tsx}', './@/**/*.{ts,tsx}'], theme: { extend: { colors: { border: 'hsl(var(--border))', ring: 'hsl(var(--ring))', background: 'hsl(var(--background))', foreground: 'hsl(var(--foreground))' } } }, plugins: [] }
