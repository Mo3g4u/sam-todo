import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { AxiosInstance } from 'axios';

// Mock axios before importing service
vi.mock('src/services/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  } as unknown as AxiosInstance,
}));

import api from 'src/services/api';
import { todoService } from 'src/services/todo.service';
import type { Todo } from 'src/types/todo';

const mockTodo: Todo = {
  id: '123',
  title: 'テストTodo',
  completed: false,
  created_at: '2026-04-10T12:00:00Z',
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe('todoService', () => {
  describe('list', () => {
    it('calls GET /todos and returns data', async () => {
      vi.mocked(api.get).mockResolvedValue({ data: [mockTodo] });

      const result = await todoService.list();

      expect(api.get).toHaveBeenCalledWith('/todos');
      expect(result).toEqual([mockTodo]);
    });
  });

  describe('get', () => {
    it('calls GET /todos/:id and returns data', async () => {
      vi.mocked(api.get).mockResolvedValue({ data: mockTodo });

      const result = await todoService.get('123');

      expect(api.get).toHaveBeenCalledWith('/todos/123');
      expect(result).toEqual(mockTodo);
    });
  });

  describe('create', () => {
    it('calls POST /todos and returns created todo', async () => {
      vi.mocked(api.post).mockResolvedValue({ data: mockTodo });

      const result = await todoService.create({ title: 'テストTodo' });

      expect(api.post).toHaveBeenCalledWith('/todos', { title: 'テストTodo' });
      expect(result).toEqual(mockTodo);
    });
  });

  describe('update', () => {
    it('calls PUT /todos/:id and returns updated todo', async () => {
      const updated = { ...mockTodo, completed: true };
      vi.mocked(api.put).mockResolvedValue({ data: updated });

      const result = await todoService.update('123', { completed: true });

      expect(api.put).toHaveBeenCalledWith('/todos/123', { completed: true });
      expect(result).toEqual(updated);
    });
  });

  describe('remove', () => {
    it('calls DELETE /todos/:id', async () => {
      vi.mocked(api.delete).mockResolvedValue({});

      await todoService.remove('123');

      expect(api.delete).toHaveBeenCalledWith('/todos/123');
    });
  });
});
