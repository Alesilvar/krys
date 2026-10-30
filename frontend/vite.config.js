import { defineConfig } from 'vite';
export default defineConfig({ define: { 'process.env.NODE_ENV': JSON.stringify('production') }, build: { outDir: '../static/react', emptyOutDir: false, lib: { entry: 'src/app.jsx', formats: ['iife'], name: 'KrysApp', fileName: () => 'app.js' } } });
