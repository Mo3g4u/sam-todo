<template>
  <q-page padding>
    <div class="q-mx-auto" style="max-width: 400px">
      <h4 class="q-mt-none q-mb-md">ログイン</h4>

      <q-banner v-if="error" class="bg-negative text-white q-mb-md" rounded>
        {{ error }}
      </q-banner>

      <q-form @submit.prevent="onSubmit" class="q-gutter-md">
        <q-input
          v-model="emailInput"
          type="email"
          label="メールアドレス"
          outlined
          :disable="loading"
        />
        <q-input
          v-model="password"
          type="password"
          label="パスワード"
          outlined
          :disable="loading"
        />
        <q-btn
          type="submit"
          color="primary"
          label="ログイン"
          class="full-width"
          :loading="loading"
          :disable="!emailInput || !password"
        />
      </q-form>

      <div class="q-mt-md text-center">
        <router-link to="/signup">アカウントを作成</router-link>
      </div>
    </div>
  </q-page>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuth } from 'src/composables/useAuth';

const router = useRouter();
const { loading, error, signIn } = useAuth();

const emailInput = ref('');
const password = ref('');

async function onSubmit() {
  try {
    await signIn(emailInput.value, password.value);
    router.push('/');
  } catch {
    // error is set by useAuth
  }
}
</script>
