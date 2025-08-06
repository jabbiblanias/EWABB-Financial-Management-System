/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
  './templates/**/*.html',
  './**/templates/**/*.html',
  './**/*.js',
  './**/*.py',
],
  theme: {
    extend: {},
  },
  plugins: [require('daisyui')],
  daisyui: {
    themes: ['light', 'dark'], // optional: customize themes here
  },
};
