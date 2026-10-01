import { createApp } from 'vue'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import 'vuetify/styles'
import '@mdi/font/css/materialdesignicons.css'
import App from './App.vue'
import router from './router'
import './styles.css'

const vuetify = createVuetify({ components, directives, theme: { defaultTheme: 'taller', themes: { taller: { dark: false, colors: { primary: '#F05040', secondary: '#F07820', accent: '#F03060', background: '#FFFFFF', surface: '#FFFFFF' } } } } })
createApp(App).use(router).use(vuetify).mount('#app')
