# Frontend コードリーディングガイド

このドキュメントは、フロントエンドのコードを上から順に読んで処理の流れを理解するためのガイドです。

---

## 読む順序

以下の順序で読むと理解しやすいです:

```
1. types/todo.ts             ← データの型を知る
2. services/api.ts           ← HTTP 通信の基盤を知る
3. services/todo.service.ts  ← API 呼び出しの具体的な内容を知る
4. composables/useTodos.ts   ← 状態管理の仕組みを知る (ここが核心)
5. components/TodoForm.vue   ← ユーザー入力の UI
6. components/TodoItem.vue   ← 1件の Todo の表示
7. components/TodoList.vue   ← Todo 一覧の表示
8. pages/TodoPage.vue        ← 全体を組み立てるページ
9. App.vue                   ← アプリのルートレイアウト
10. router/                  ← ルーティング設定
```

---

## 全体のデータフロー

コードを読む前に、アプリ全体のデータの流れを把握しておくと理解が早くなります。

```
ユーザー操作 (入力、クリック)
    ↓ emit (イベント)
TodoForm / TodoItem (UI コンポーネント)
    ↓ emit (イベント)
TodoPage.vue (ページ)
    ↓ 関数呼び出し
useTodos() composable (状態管理)
    ↓ 関数呼び出し
todoService (API 通信)
    ↓ HTTP リクエスト
api.ts (axios インスタンス)
    ↓ HTTPS
Backend API (Lambda + DynamoDB)
```

**ポイント**: UI コンポーネント (TodoForm, TodoItem, TodoList) は API を直接呼びません。イベントを親に伝え、最終的に `useTodos()` composable が API を呼びます。

---

## 1. types/todo.ts — 型定義

```typescript
export interface Todo {
  id: string;
  title: string;
  completed: boolean;
  created_at: string;
  updated_at?: string;
}

export interface CreateTodoRequest {
  title: string;
}

export interface UpdateTodoRequest {
  title?: string;
  completed?: boolean;
}
```

### 解説

TypeScript のインターフェースでデータの形を定義します。

| インターフェース | 用途 | 補足 |
|---|---|---|
| `Todo` | API から返ってくる Todo データの型 | `updated_at?` の `?` はオプショナル (あってもなくてもよい) |
| `CreateTodoRequest` | Todo 作成時に送るデータの型 | `title` だけ必要 |
| `UpdateTodoRequest` | Todo 更新時に送るデータの型 | `title` と `completed` のどちらか (または両方) |

これらの型は、以降のすべてのファイルで「関数の引数・戻り値が何か」を明確にするために使われます。

---

## 2. services/api.ts — axios インスタンス

```typescript
import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL as string,
  headers: { 'Content-Type': 'application/json' },
});

export default api;
```

### 解説

**役割**: HTTP リクエストを送るための設定済み axios インスタンスを作成する。

**`import.meta.env.VITE_API_URL`**: Vite の環境変数。ビルド時に `.env.development` または `.env.production` から読み込まれます。

| 環境 | 値 | 読み込み元 |
|---|---|---|
| ローカル開発 | `http://localhost:3000` | `.env.development` |
| 本番 | `https://xxx.execute-api.ap-northeast-1.amazonaws.com/dev` | Amplify ビルド時に `.env.production` へ注入 |

**`baseURL`**: 以降の API 呼び出しで `/todos` と書けば `http://localhost:3000/todos` になります。

---

## 3. services/todo.service.ts — API 呼び出し

```typescript
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
```

### 解説

**役割**: Backend API への CRUD 操作を薄くラップしたサービスオブジェクト。

各メソッドと Backend ハンドラーの対応:

| メソッド | HTTP リクエスト | Backend ハンドラー |
|---|---|---|
| `list()` | `GET /todos` | `list_todos.handler` |
| `get(id)` | `GET /todos/{id}` | `get_todo.handler` |
| `create(req)` | `POST /todos` | `create_todo.handler` |
| `update(id, req)` | `PUT /todos/{id}` | `update_todo.handler` |
| `remove(id)` | `DELETE /todos/{id}` | `delete_todo.handler` |

**`const { data } = await api.get<Todo[]>(...)`**: axios のレスポンスから `data` プロパティだけを取り出す分割代入。`<Todo[]>` はレスポンスの型指定 (TypeScript のジェネリクス)。

**なぜ `remove` で `delete` でないか**: `delete` は JavaScript の予約語のため、メソッド名として `remove` を使用しています。内部では `api.delete()` を呼んでいます。

---

## 4. composables/useTodos.ts — 状態管理 (核心)

```typescript
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
```

### 解説

**役割**: アプリの状態 (todos, loading, error) と、それを変更する関数をまとめた Composition API の composable。

**`ref<T>(初期値)`**: Vue 3 のリアクティブ変数。値が変わると UI が自動で再描画されます。

### 状態 (リアクティブ変数)

| 変数 | 型 | 初期値 | 用途 |
|---|---|---|---|
| `todos` | `Ref<Todo[]>` | `[]` | Todo 一覧 |
| `loading` | `Ref<boolean>` | `false` | API 通信中フラグ |
| `error` | `Ref<string \| null>` | `null` | エラーメッセージ (日本語) |

### 各関数の詳細

**fetchTodos() — 一覧取得**:
```
1. loading = true (スピナー表示)
2. todoService.list() で API を呼ぶ
3. 成功 → todos に結果を代入
   失敗 → error にエラーメッセージを設定
4. loading = false (スピナー非表示)
```

**addTodo(title) — 新規作成**:
```
1. todoService.create({title}) で API を呼ぶ
2. 成功 → todos.unshift(todo) で先頭に追加
   (unshift = 配列の先頭に挿入。push は末尾)
```

**toggleTodo(todo) — 完了/未完了の切り替え**:
```
1. todoService.update(id, {completed: !todo.completed}) で API を呼ぶ
   (!todo.completed で true/false を反転)
2. 成功 → 配列内の該当 Todo を更新後のデータで差し替え
   (findIndex で位置を特定し、直接代入)
```

**removeTodo(id) — 削除**:
```
1. todoService.remove(id) で API を呼ぶ
2. 成功 → todos.filter() で該当 Todo を除外した新しい配列に差し替え
```

**なぜ API 成功後にローカルの配列も更新するか**: API レスポンスを待ってから `fetchTodos()` で全件再取得することもできますが、UX が悪くなります (一瞬全部消えてから再表示される)。ローカルの配列を直接操作することで、即座に UI に反映されます。

---

## 5. components/TodoForm.vue — Todo 入力フォーム

```vue
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
```

### 解説

**テンプレート部分**:
- `@submit.prevent="onSubmit"`: フォーム送信時に `onSubmit` を呼ぶ。`.prevent` はブラウザのデフォルト動作 (ページリロード) を防止
- `v-model="title"`: 入力フィールドと `title` 変数を双方向バインド
- `:disable="!title.trim()"`: 空文字のときは追加ボタンを無効化
- `:loading="loading"`: API 通信中はボタンにスピナー表示

**スクリプト部分**:
- `defineEmits`: このコンポーネントが発火できるイベントの型定義
- `defineProps`: 親から受け取るプロパティの型定義
- `emit('add', value)`: 親コンポーネント (TodoPage) にイベントを送る

**コンポーネント内で API を呼ばない理由**: 関心の分離。フォームは「ユーザー入力を受け取ってイベントを発火する」だけの責務。API 呼び出しは composable が担当します。

---

## 6. components/TodoItem.vue — 1件の Todo 表示

```vue
<template>
  <q-item>
    <q-item-section side>
      <q-checkbox
        :model-value="todo.completed"
        @update:model-value="$emit('toggle', todo)"
      />
    </q-item-section>

    <q-item-section :class="{ 'text-strike text-grey': todo.completed }">
      {{ todo.title }}
    </q-item-section>

    <q-item-section side>
      <q-btn flat round dense icon="delete" color="negative"
        @click="$emit('remove', todo.id)"
      />
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
```

### 解説

**3つのセクション**:
```
┌──────────────────────────────────────────────┐
│ [✓]  │  買い物に行く  │  🗑️                  │
│チェック│   タイトル      │  削除ボタン          │
│ (side)│   (メイン)      │  (side)              │
└──────────────────────────────────────────────┘
```

**`:model-value` と `@update:model-value`**: `v-model` を分解した形。チェックボックスの状態変更時に `toggle` イベントを親に送ります。`v-model` を使わない理由は、チェック状態の変更を親 (→ composable → API) 経由で行いたいからです。

**`:class="{ 'text-strike text-grey': todo.completed }"`**: 条件付き CSS クラス。`completed` が `true` のとき取り消し線 (`text-strike`) とグレー文字 (`text-grey`) を適用します。

**`$emit('remove', todo.id)`**: テンプレート内で直接イベントを発火。`script` 内の `emit()` と同じ動作です。

---

## 7. components/TodoList.vue — Todo 一覧表示

```vue
<template>
  <div>
    <q-spinner v-if="loading" size="3em" color="primary"
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
```

### 解説

**3つの状態で表示を切り替え**:

```
v-if="loading"               → スピナー (API 通信中)
v-else-if="todos.length===0" → 「Todoはまだありません」
v-else                       → Todo リスト
```

**`v-for="todo in todos" :key="todo.id"`**: `todos` 配列をループして `TodoItem` を繰り返し描画。`:key` は Vue が各要素を効率的に追跡するための一意識別子。

**イベントの中継**: `@toggle="$emit('toggle', $event)"` で、子 (TodoItem) のイベントをそのまま親 (TodoPage) に中継しています。`$event` はイベントの引数を指します。

---

## 8. pages/TodoPage.vue — メインページ

```vue
<template>
  <q-page padding>
    <div class="q-mx-auto" style="max-width: 600px">
      <h4 class="q-mt-none q-mb-md">Todo App</h4>

      <q-banner v-if="error" class="bg-negative text-white q-mb-md" rounded>
        {{ error }}
      </q-banner>

      <TodoForm :loading="loading" @add="addTodo" />
      <TodoList :todos="todos" :loading="loading"
        @toggle="toggleTodo" @remove="removeTodo"
      />
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
```

### 解説

**このコンポーネントが「接着剤」**: composable とUIコンポーネントを接続する役割です。

```
useTodos() から取得:
  状態:  todos, loading, error     → テンプレートで参照
  関数:  addTodo, toggleTodo, removeTodo → イベントハンドラとして接続

TodoForm:
  props:  :loading         ← useTodos().loading
  events: @add             → useTodos().addTodo

TodoList:
  props:  :todos, :loading ← useTodos().todos, useTodos().loading
  events: @toggle          → useTodos().toggleTodo
          @remove          → useTodos().removeTodo
```

**`onMounted(fetchTodos)`**: ページが DOM にマウントされたタイミングで `fetchTodos` を呼び出し、初期データを取得します。

**エラー表示**: `error` が `null` でないとき、赤いバナー (`bg-negative`) でエラーメッセージを表示します。

---

## 9. App.vue — アプリのルート

```vue
<template>
  <q-layout view="hHh lpR fFf">
    <q-header elevated class="bg-primary text-white">
      <q-toolbar>
        <q-toolbar-title>SAM Todo App</q-toolbar-title>
      </q-toolbar>
    </q-header>

    <q-page-container>
      <router-view />
    </q-page-container>
  </q-layout>
</template>
```

### 解説

**Quasar レイアウトシステム**:

```
┌──────────────────────────────────────┐
│ q-header: "SAM Todo App"             │  ← 固定ヘッダー
├──────────────────────────────────────┤
│ q-page-container                     │
│   └── router-view                    │  ← ここにページが表示される
│         └── TodoPage.vue             │
│               ├── TodoForm.vue       │
│               └── TodoList.vue       │
└──────────────────────────────────────┘
```

**`view="hHh lpR fFf"`**: Quasar のレイアウト文字列。ヘッダー・ドロワー・フッターの配置を制御します。`hHh` = ヘッダーが全幅表示。

**`<router-view />`**: Vue Router が現在の URL に応じたコンポーネントをここに描画します。`/` なら `TodoPage.vue` が表示されます。

**なぜ `<q-page>` が必要か**: Quasar は `<q-layout>` > `<q-page-container>` > `<q-page>` という階層を要求します。`<q-page>` なしだと何も描画されません (真っ白画面)。

---

## 10. router/ — ルーティング

### routes.ts

```typescript
import type { RouteRecordRaw } from 'vue-router';
import TodoPage from 'src/pages/TodoPage.vue';

const routes: RouteRecordRaw[] = [{ path: '/', component: TodoPage }];

export default routes;
```

URL `/` にアクセスすると `TodoPage` を表示する、というルーティング定義です。

### index.ts

```typescript
import { createRouter, createMemoryHistory, createWebHashHistory, createWebHistory } from 'vue-router';
import routes from './routes';

export default function () {
  const createHistory = process.env.SERVER
    ? createMemoryHistory
    : process.env.VUE_ROUTER_MODE === 'history'
      ? createWebHistory
      : createWebHashHistory;

  return createRouter({
    scrollBehavior: () => ({ left: 0, top: 0 }),
    routes,
    history: createHistory(process.env.VUE_ROUTER_BASE),
  });
}
```

**履歴モードの選択**:
- SSR (サーバーサイドレンダリング): `createMemoryHistory` (ブラウザ API 不要)
- History モード: `createWebHistory` → URL が `/todos` のようにきれい
- Hash モード: `createWebHashHistory` → URL が `/#/todos` になる

Quasar の設定 (`quasar.config.ts` の `vueRouterMode: 'history'`) で History モードを指定しています。

---

## テストの読み方

### サービスのテスト (todo.service.test.ts)

```typescript
// axios の api モジュールをモック化
vi.mock('src/services/api', () => ({
  default: {
    get: vi.fn(),    // api.get() がモック関数になる
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));
```

**テストの目的**: `todoService.list()` が `api.get('/todos')` を呼んで、レスポンスの `data` を返すことを検証。実際の HTTP 通信は行いません。

```typescript
it('calls GET /todos and returns data', async () => {
  // 準備: api.get() が呼ばれたら mockTodo の配列を返す
  vi.mocked(api.get).mockResolvedValue({ data: [mockTodo] });

  // 実行
  const result = await todoService.list();

  // 検証
  expect(api.get).toHaveBeenCalledWith('/todos');  // 正しいパスで呼ばれたか
  expect(result).toEqual([mockTodo]);               // 正しいデータが返るか
});
```

### Composable のテスト (useTodos.test.ts)

```typescript
// todoService モジュールをモック化
vi.mock('src/services/todo.service', () => ({
  todoService: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
  },
}));
```

**テストの目的**: `useTodos()` が `todoService` を正しく呼び、リアクティブ状態 (`todos`, `loading`, `error`) を正しく更新することを検証。

```typescript
it('loads todos and sets loading state', async () => {
  vi.mocked(todoService.list).mockResolvedValue(mockTodos);

  const { todos, loading, fetchTodos } = useTodos();

  expect(loading.value).toBe(false);     // 初期状態: loading = false
  const promise = fetchTodos();
  expect(loading.value).toBe(true);      // 呼び出し直後: loading = true

  await promise;
  expect(loading.value).toBe(false);     // 完了後: loading = false
  expect(todos.value).toEqual(mockTodos); // todos にデータが入っている
});
```

**テスト階層**: サービスのテストは「HTTP 呼び出しの正しさ」、composable のテストは「状態管理の正しさ」をそれぞれ独立して検証しています。
