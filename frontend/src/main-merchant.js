import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import './styles/tokens.css'
import './styles/element-overrides.css'
import './styles/global.css'
import './styles/animations.css'
import zhCn from 'element-plus/es/locale/lang/zh-cn.mjs'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import App from './App.vue'
import router from './router/merchant'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: zhCn })
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}
app.config.errorHandler = (err, instance, info) => {
  console.error('[Vue errorHandler]', err, info)
  // Show error visually so white screen is diagnosed
  const el = document.getElementById('app')
  if (el && !el.innerHTML.trim()) {
    el.innerHTML = '<div style=\"padding:40px;color:#e74c3c;font-family:monospace\"><h2>Vue Error</h2><pre>' +
      String(err).replace(/&/g,'&amp;').replace(/</g,'&lt;') + '</pre></div>'
  }
}
try {
  app.mount('#app')
  console.log('[main-merchant] Vue mounted successfully')
} catch (e) {
  console.error('[main-merchant] Mount failed:', e)
  document.getElementById('app').innerHTML = '<div style=\"padding:40px;color:#e74c3c;font-family:monospace\"><h2>Mount Error</h2><pre>' +
    String(e).replace(/&/g,'&amp;').replace(/</g,'&lt;') + '</pre></div>'
}
