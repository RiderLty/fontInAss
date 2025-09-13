import { createApp } from 'vue';
import { createI18n } from "vue-i18n";
import './style.css';
import App from './App.vue';
import zhCN from "./locales/zh-CN.json";
import enUS from "./locales/en-US.json";

const messages = {
    "zh-CN": zhCN,
    "en-US": enUS,
};

const i18n = createI18n({
    legacy: false, // composition API 模式
    locale: localStorage.getItem("locale") || "zh-CN",
    fallbackLocale: "en-US",
    missingWarn: false, // 关闭 missing key 警告
    fallbackWarn: false, // 关闭 fallback 警告
    messages,
});

createApp(App).use(i18n).mount('#app')
