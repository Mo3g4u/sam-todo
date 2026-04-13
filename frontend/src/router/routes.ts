import type { RouteRecordRaw } from 'vue-router';
import TodoPage from 'src/pages/TodoPage.vue';
import LoginPage from 'src/pages/LoginPage.vue';
import SignupPage from 'src/pages/SignupPage.vue';

const routes: RouteRecordRaw[] = [
  { path: '/login', component: LoginPage },
  { path: '/signup', component: SignupPage },
  { path: '/', component: TodoPage, meta: { requiresAuth: true } },
];

export default routes;
