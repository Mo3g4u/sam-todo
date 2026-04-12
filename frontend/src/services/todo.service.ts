import api from 'src/services/api';
import type { Todo, CreateTodoRequest, UpdateTodoRequest } from 'src/types/todo';

export const todoService = {
  async list(): Promise<Todo[]> {
    const { data } = await api.get<Todo[]>('/todos');
    return data;
  },

  async get(id: string): Promise<Todo> {
    const { data } = await api.get<Todo>(`/todos/${id}`);
    return data;
  },

  async create(req: CreateTodoRequest): Promise<Todo> {
    const { data } = await api.post<Todo>('/todos', req);
    return data;
  },

  async update(id: string, req: UpdateTodoRequest): Promise<Todo> {
    const { data } = await api.put<Todo>(`/todos/${id}`, req);
    return data;
  },

  async remove(id: string): Promise<void> {
    await api.delete(`/todos/${id}`);
  },
};
