<template>
  <q-item>
    <q-item-section side>
      <q-checkbox :model-value="todo.completed" @update:model-value="$emit('toggle', todo)" />
    </q-item-section>

    <q-item-section :class="{ 'text-strike text-grey': todo.completed }">
      {{ todo.title }}
    </q-item-section>

    <q-item-section side>
      <q-btn flat round dense icon="delete" color="negative" @click="$emit('remove', todo.id)" />
    </q-item-section>
  </q-item>
</template>

<script setup lang="ts">
import type { Todo } from 'src/types/todo';

defineProps<{
  todo: Todo;
}>();

defineEmits<{
  toggle: [todo: Todo];
  remove: [id: string];
}>();
</script>
