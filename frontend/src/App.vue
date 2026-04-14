<template>
  <q-layout view="hHh lpR fFf">
    <q-header elevated class="bg-primary text-white">
      <q-toolbar>
        <q-toolbar-title>SAM Todo App</q-toolbar-title>
        <q-space />
        <template v-if="isAuthenticated">
          <span class="q-mr-sm">{{ email }}</span>
          <q-btn flat label="ログアウト" @click="onLogout" />
        </template>
      </q-toolbar>
    </q-header>

    <q-page-container>
      <router-view />
    </q-page-container>
  </q-layout>
</template>

<script setup lang="ts">
import { onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useAuth } from 'src/composables/useAuth';

const router = useRouter();
const { email, isAuthenticated, checkSession, signOut } = useAuth();

onMounted(checkSession);

function onLogout() {
  signOut();
  router.push('/login');
}
</script>
