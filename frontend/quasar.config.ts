import { defineConfig } from '#q-app/wrappers';

export default defineConfig(() => {
  return {
    boot: [],
    css: ['app.scss'],
    extras: ['material-icons'],
    build: {
      target: { browser: ['es2022', 'firefox115', 'chrome115', 'safari14'] },
      vueRouterMode: 'history',
      vitePlugins: [],
    },
    devServer: {
      open: false,
      port: 9000,
    },
    framework: {
      plugins: ['Notify'],
    },
  };
});
