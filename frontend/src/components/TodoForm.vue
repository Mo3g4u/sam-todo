<template>
  <q-form @submit.prevent="onSubmit" class="q-mb-md">
    <div class="row q-gutter-sm items-center">
      <q-input
        v-model="title"
        dense
        outlined
        placeholder="新しいTodoを入力..."
        class="col"
        :disable="loading"
      />
      <q-btn
        type="submit"
        color="primary"
        label="追加"
        :loading="loading"
        :disable="!title.trim()"
      />
    </div>
  </q-form>
</template>

<script setup lang="ts">
import { ref } from 'vue';

const emit = defineEmits<{
  add: [title: string];
}>();

defineProps<{
  loading?: boolean;
}>();

const title = ref('');

function onSubmit() {
  const value = title.value.trim();
  if (!value) return;
  emit('add', value);
  title.value = '';
}
</script>
