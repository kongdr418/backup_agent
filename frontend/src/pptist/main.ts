import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'

import 'prosemirror-view/style/prosemirror.css'
import 'animate.css'
import '@pptist/assets/styles/prosemirror.scss'
import '@pptist/assets/styles/global.scss'
import '@pptist/assets/styles/font.scss'

import Directive from '@pptist/directive'

const app = createApp(App)
app.use(Directive)
app.use(createPinia())
app.mount('#app')
