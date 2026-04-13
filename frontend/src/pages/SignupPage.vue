<template>
  <q-page padding>
    <div class="q-mx-auto" style="max-width: 400px">
      <h4 class="q-mt-none q-mb-md">{{ showConfirm ? '確認コード入力' : 'アカウント作成' }}</h4>

      <q-banner v-if="error" class="bg-negative text-white q-mb-md" rounded>
        {{ error }}
      </q-banner>

      <!-- サインアップフォーム -->
      <q-form v-if="!showConfirm" @submit.prevent="onSignUp" class="q-gutter-md">
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
          label="パスワード (8文字以上、大小英数字)"
          outlined
          :disable="loading"
        />
        <q-btn
          type="submit"
          color="primary"
          label="アカウント作成"
          class="full-width"
          :loading="loading"
          :disable="!emailInput || !password"
        />
      </q-form>

      <!-- 確認コードフォーム -->
      <q-form v-else @submit.prevent="onConfirm" class="q-gutter-md">
        <p>{{ emailInput }} に確認コードを送信しました。</p>
        <q-input v-model="confirmCode" label="確認コード" outlined :disable="loading" />
        <q-btn
          type="submit"
          color="primary"
          label="確認"
          class="full-width"
          :loading="loading"
          :disable="!confirmCode"
        />
      </q-form>

      <div class="q-mt-md text-center">
        <router-link to="/login">ログインに戻る</router-link>
      </div>
    </div>
  </q-page>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuth } from 'src/composables/useAuth';

const router = useRouter();
const { loading, error, signUp, confirmSignUp } = useAuth();

const emailInput = ref('');
const password = ref('');
const confirmCode = ref('');
const showConfirm = ref(false);

async function onSignUp() {
  try {
    await signUp(emailInput.value, password.value);
    showConfirm.value = true;
  } catch {
    // error is set by useAuth
  }
}

async function onConfirm() {
  try {
    await confirmSignUp(emailInput.value, confirmCode.value);
    router.push('/login');
  } catch {
    // error is set by useAuth
  }
}
</script>
