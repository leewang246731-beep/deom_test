import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import App from './App.vue'
import router from './router'
const app = createApp(App)
app.use(createPinia()); app.use(router); app.use(ElementPlus)
app.config.errorHandler = (err, instance, info) => { console.error('[vMall Admin errorHandler]', err, info) }
app.mount('#app')
