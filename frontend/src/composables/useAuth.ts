import { ref, computed } from 'vue';
import { authService } from 'src/services/auth.service';

const email = ref<string | null>(null);
const loading = ref(false);
const error = ref<string | null>(null);

export function useAuth() {
  const isAuthenticated = computed(() => email.value !== null);

  async function checkSession() {
    const session = await authService.getSession();
    if (session) {
      email.value = session.getIdToken().payload['email'] as string;
    } else {
      email.value = null;
    }
  }

  async function signUp(emailAddr: string, password: string) {
    loading.value = true;
    error.value = null;
    try {
      await authService.signUp(emailAddr, password);
    } catch (e) {
      error.value = (e as Error).message || 'サインアップに失敗しました';
      throw e;
    } finally {
      loading.value = false;
    }
  }

  async function confirmSignUp(emailAddr: string, code: string) {
    loading.value = true;
    error.value = null;
    try {
      await authService.confirmSignUp(emailAddr, code);
    } catch (e) {
      error.value = (e as Error).message || '確認コードの検証に失敗しました';
      throw e;
    } finally {
      loading.value = false;
    }
  }

  async function signIn(emailAddr: string, password: string) {
    loading.value = true;
    error.value = null;
    try {
      const session = await authService.signIn(emailAddr, password);
      email.value = session.getIdToken().payload['email'] as string;
    } catch (e) {
      error.value = (e as Error).message || 'ログインに失敗しました';
      throw e;
    } finally {
      loading.value = false;
    }
  }

  function signOut() {
    authService.signOut();
    email.value = null;
  }

  return {
    email,
    loading,
    error,
    isAuthenticated,
    checkSession,
    signUp,
    confirmSignUp,
    signIn,
    signOut,
  };
}
