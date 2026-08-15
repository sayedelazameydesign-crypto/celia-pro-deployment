import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { visualizer } from 'rollup-plugin-visualizer'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    // Bundle analyzer - generates stats.html
    // Enable with: npm run build:analyze
    process.env.ANALYZE === 'true' && visualizer({
      filename: 'dist/bundle-stats.html',
      gzipSize: true,
      brotliSize: true,
      title: 'celia.pro Bundle Analysis',
      template: 'treemap',
    }) as any,
  ].filter(Boolean),

  build: {
    // Enable source maps for production debugging
    sourcemap: false,
    
    // CSS code splitting
    cssCodeSplit: true,
    
    // Target modern browsers for smaller output
    target: 'es2020',
    
    // Minification with esbuild (default)
    minify: 'esbuild',
    
    // Chunk size warning threshold (1MB)
    chunkSizeWarningLimit: 1000,
    
    // Rollup configuration for code splitting
    rollupOptions: {
      output: {
        // Manual chunks to separate vendor libraries
        // Using function form for TypeScript compatibility
        manualChunks(id: string) {
          if (id.includes('node_modules')) {
            if (id.includes('react-dom') || id.includes('react/')) {
              return 'react-vendor'
            }
            if (id.includes('react-router-dom')) {
              return 'router-vendor'
            }
            if (id.includes('lucide-react')) {
              return 'icons'
            }
            if (id.includes('react-hot-toast')) {
              return 'toast'
            }
            if (id.includes('react-markdown') || id.includes('unified') || id.includes('remark')) {
              return 'markdown'
            }
          }
        },
        
        // Asset file naming with hash for cache busting
        chunkFileNames: 'assets/js/[name]-[hash].js',
        entryFileNames: 'assets/js/[name]-[hash].js',
        assetFileNames: (assetInfo: any) => {
          const name = assetInfo.name || ''
          if (name.endsWith('.css')) {
            return 'assets/css/[name]-[hash][extname]'
          }
          if (/\.(png|jpe?g|gif|svg|webp|ico)$/.test(name)) {
            return 'assets/images/[name]-[hash][extname]'
          }
          return 'assets/[name]-[hash][extname]'
        },
      },
    },
  },

  server: {
    host: '0.0.0.0',
    port: 5173,
    allowedHosts: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
})
