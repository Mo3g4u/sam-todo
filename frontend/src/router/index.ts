import {
  createRouter,
  createMemoryHistory,
  createWebHashHistory,
  createWebHistory,
} from 'vue-router';
import routes from './routes';
import { authService } from 'src/services/auth.service';

export default function () {
  const createHistory = process.env.SERVER
    ? createMemoryHistory
    : process.env.VUE_ROUTER_MODE === 'history'
      ? createWebHistory
      : createWebHashHistory;

  const router = createRouter({
    scrollBehavior: () => ({ left: 0, top: 0 }),
    routes,
    history: createHistory(process.env.VUE_ROUTER_BASE),
  });

  router.beforeEach(async (to) => {
    if (to.meta.requiresAuth) {
      const session = await authService.getSession();
      if (!session) {
        return { path: '/login' };
      }
    }
  });

  return router;
}
