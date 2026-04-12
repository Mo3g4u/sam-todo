<template>
  <div>
    <q-spinner
      v-if="loading"
      size="3em"
      color="primary"
      class="q-my-md full-width flex flex-center"
    />

    <div v-else-if="todos.length === 0" class="text-grey text-center q-pa-lg">
      Todoはまだありません
    </div>

    <q-list v-else separator>
      <TodoItem
        v-for="todo in todos"
        :key="todo.id"
        :todo="todo"
        @toggle="$emit('toggle', $event)"
        @remove="$emit('remove', $event)"
      />
    </q-list>
  </div>
</template>

<script setup lang="ts">
import type { Todo } from 'src/types/todo';
import TodoItem from 'src/components/TodoItem.vue';

defineProps<{
  todos: Todo[];
  loading: boolean;
}>();

defineEmits<{
  toggle: [todo: Todo];
  remove: [id: string];
}>();
</script>
