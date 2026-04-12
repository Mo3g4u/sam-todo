import { ref } from 'vue';
import type { Todo } from 'src/types/todo';
import { todoService } from 'src/services/todo.service';

export function useTodos() {
  const todos = ref<Todo[]>([]);
  const loading = ref(false);
  const error = ref<string | null>(null);

  async function fetchTodos() {
    loading.value = true;
    error.value = null;
    try {
      todos.value = await todoService.list();
    } catch {
      error.value = 'Todoの取得に失敗しました';
    } finally {
      loading.value = false;
    }
  }

  async function addTodo(title: string) {
    error.value = null;
    try {
      const todo = await todoService.create({ title });
      todos.value.unshift(todo);
    } catch {
      error.value = 'Todoの作成に失敗しました';
    }
  }

  async function toggleTodo(todo: Todo) {
    error.value = null;
    try {
      const updated = await todoService.update(todo.id, {
        completed: !todo.completed,
      });
      const idx = todos.value.findIndex((t) => t.id === todo.id);
      if (idx !== -1) todos.value[idx] = updated;
    } catch {
      error.value = 'Todoの更新に失敗しました';
    }
  }

  async function removeTodo(id: string) {
    error.value = null;
    try {
      await todoService.remove(id);
      todos.value = todos.value.filter((t) => t.id !== id);
    } catch {
      error.value = 'Todoの削除に失敗しました';
    }
  }

  return { todos, loading, error, fetchTodos, addTodo, toggleTodo, removeTodo };
}
