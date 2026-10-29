import { createApp } from 'vue'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import 'vuetify/styles'
import '@mdi/font/css/materialdesignicons.css'
import App from './App.vue'
import router from './router'
import './styles.css'

const field = { variant: 'outlined', density: 'comfortable', color: 'primary' } as const
const vuetify = createVuetify({
  components,
  directives,
  defaults: { VTextField: field, VSelect: field, VTextarea: field, VBtn: { rounded: 'lg' }, VAlert: { rounded: 'lg' } },
  theme: {
    defaultTheme: 'taller',
    themes: {
      taller: { dark: false, colors: { primary: '#F05040', secondary: '#F07820', accent: '#F03060', background: '#F4F5F9', surface: '#FFFFFF', success: '#1E9E62', info: '#2F6FE4', warning: '#E08A00', error: '#D93A2B' } },
      tallerDark: { dark: true, colors: { primary: '#FF7A63', secondary: '#F07820', background: '#17181D', surface: '#17181D' } }
    }
  }
})
createApp(App).use(router).use(vuetify).mount('#app')
