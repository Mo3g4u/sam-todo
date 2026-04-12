<template>
  <q-page padding>
    <div class="q-mx-auto" style="max-width: 600px">
      <h4 class="q-mt-none q-mb-md">Todo App</h4>

      <q-banner v-if="error" class="bg-negative text-white q-mb-md" rounded>
        {{ error }}
      </q-banner>

      <TodoForm :loading="loading" @add="addTodo" />
      <TodoList :todos="todos" :loading="loading" @toggle="toggleTodo" @remove="removeTodo" />
    </div>
  </q-page>
</template>

<script setup lang="ts">
import { onMounted } from 'vue';
import { useTodos } from 'src/composables/useTodos';
import TodoForm from 'src/components/TodoForm.vue';
import TodoList from 'src/components/TodoList.vue';

const { todos, loading, error, fetchTodos, addTodo, toggleTodo, removeTodo } = useTodos();

onMounted(fetchTodos);
</script>
