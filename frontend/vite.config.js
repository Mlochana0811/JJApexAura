import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import {defineConfig} from 'vite';
import path from 'node:path';
export default defineConfig({plugins:[react(),tailwindcss()],resolve:{alias:{'@':path.resolve(import.meta.dirname,'src')}},server:{host:'127.0.0.1',proxy:Object.fromEntries(['/api','/admin','/login','/logout','/password','/branding','/payroll','/payslip','/static','/media'].map(p=>[p,{target:'http://127.0.0.1:8000',changeOrigin:true}]))}});
