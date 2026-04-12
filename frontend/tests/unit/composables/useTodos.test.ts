import { describe, it, expect, vi, beforeEach } from 'vitest';
import { flushPromises } from '@vue/test-utils';
import type { Todo } from 'src/types/todo';

const mockTodos: Todo[] = [
  { id: '1', title: 'Todo 1', completed: false, created_at: '2026-04-10T12:00:00Z' },
  { id: '2', title: 'Todo 2', completed: true, created_at: '2026-04-10T13:00:00Z' },
];

vi.mock('src/services/todo.service', () => ({
  todoService: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
  },
}));

import { todoService } from 'src/services/todo.service';
import { useTodos } from 'src/composables/useTodos';

beforeEach(() => {
  vi.clearAllMocks();
});

describe('useTodos', () => {
  describe('fetchTodos', () => {
    it('loads todos and sets loading state', async () => {
      vi.mocked(todoService.list).mockResolvedValue(mockTodos);

      const { todos, loading, fetchTodos } = useTodos();

      expect(loading.value).toBe(false);
      const promise = fetchTodos();
      expect(loading.value).toBe(true);

      await promise;
      expect(loading.value).toBe(false);
      expect(todos.value).toEqual(mockTodos);
    });

    it('sets error on failure', async () => {
      vi.mocked(todoService.list).mockRejectedValue(new Error('Network error'));

      const { error, fetchTodos } = useTodos();
      await fetchTodos();

      expect(error.value).toBe('Todoの取得に失敗しました');
    });
  });

  describe('addTodo', () => {
    it('creates todo and prepends to list', async () => {
      const newTodo: Todo = {
        id: '3',
        title: '新しいTodo',
        completed: false,
        created_at: '2026-04-10T14:00:00Z',
      };
      vi.mocked(todoService.create).mockResolvedValue(newTodo);
      vi.mocked(todoService.list).mockResolvedValue([]);

      const { todos, addTodo, fetchTodos } = useTodos();
      await fetchTodos();
      await addTodo('新しいTodo');

      expect(todoService.create).toHaveBeenCalledWith({ title: '新しいTodo' });
      expect(todos.value[0]).toEqual(newTodo);
    });
  });

  describe('toggleTodo', () => {
    it('toggles completed state', async () => {
      const toggled = { ...mockTodos[0], completed: true };
      vi.mocked(todoService.list).mockResolvedValue([{ ...mockTodos[0] }]);
      vi.mocked(todoService.update).mockResolvedValue(toggled);

      const { todos, toggleTodo, fetchTodos } = useTodos();
      await fetchTodos();
      await toggleTodo(todos.value[0]);

      expect(todoService.update).toHaveBeenCalledWith('1', { completed: true });
      expect(todos.value[0].completed).toBe(true);
    });
  });

  describe('removeTodo', () => {
    it('removes todo from list', async () => {
      vi.mocked(todoService.list).mockResolvedValue([...mockTodos]);
      vi.mocked(todoService.remove).mockResolvedValue();

      const { todos, removeTodo, fetchTodos } = useTodos();
      await fetchTodos();
      await removeTodo('1');

      expect(todoService.remove).toHaveBeenCalledWith('1');
      expect(todos.value).toHaveLength(1);
      expect(todos.value[0].id).toBe('2');
    });
  });
});
