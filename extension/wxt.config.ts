import { defineConfig } from 'wxt';

export default defineConfig({
  modules: ['@wxt-dev/module-react'],
  manifest: {
    name: 'Screen to Cart',
    description: 'Find anything you see in a video, compared across stores.',
    permissions: ['sidePanel'],
  },
});
