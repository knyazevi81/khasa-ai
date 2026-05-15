/**
 * Тонкий HTTP-клиент для khasa-backend.
 *
 * Поведение:
 *  • базовый URL берётся из NEXT_PUBLIC_API_URL (обычно "/api"),
 *  • в браузере подставляет Bearer-токен из tokenStorage,
 *  • на 401 → 1 раз пробует /auth/refresh и повторяет запрос,
 *  • ошибки нормализует в { status, code, detail }.
 */

import { tokenStorage } from "./token-storage";
import type {
  ApiError,
  MessageDTO,
  TokenPairDTO,
  UserDTO,
  UsersListDTO,
} from "./api-types";
import type {
  ArtifactDTO,
  ArtifactDetailDTO,
  ArtifactListDTO,
  ChatDTO,
  ChatsListDTO,
  FileEntryDTO,
  LLMCredentialDTO,
  LLMCredentialsListDTO,
  MCPServerDTO,
  MessageDTO as ChatMessageDTO,
  MessagesListDTO,
  ParsedFileDTO,
  SandboxDTO,
  SystemPromptDTO,
  SystemPromptListDTO,
} from "./chat-types";

const BASE = process.env.NEXT_PUBLIC_API_URL || "/api";

interface RequestOpts {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  auth?: boolean; // подставить Bearer
  signal?: AbortSignal;
}

class ApiHttpError extends Error implements ApiError {
  status: number;
  code: number;
  detail: string;

  constructor(status: number, code: number, detail: string) {
    super(detail);
    this.status = status;
    this.code = code;
    this.detail = detail;
  }
}

async function rawRequest<T>(path: string, opts: RequestOpts = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (opts.auth && typeof window !== "undefined") {
    const token = tokenStorage.access;
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  const resp = await fetch(`${BASE}/v1${path}`, {
    method: opts.method ?? "GET",
    headers,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
    signal: opts.signal,
    cache: "no-store",
  });

  if (resp.status === 204) {
    return undefined as T;
  }

  let payload: unknown = null;
  const ct = resp.headers.get("content-type") || "";
  if (ct.includes("application/json")) {
    payload = await resp.json().catch(() => null);
  }

  if (!resp.ok) {
    const detail =
      (payload as { detail?: string } | null)?.detail ?? `HTTP ${resp.status}`;
    const code =
      (payload as { code?: number } | null)?.code ?? resp.status;
    throw new ApiHttpError(resp.status, code, detail);
  }

  return payload as T;
}

let refreshing: Promise<void> | null = null;

async function tryRefresh(): Promise<boolean> {
  if (typeof window === "undefined") return false;
  const refresh = tokenStorage.refresh;
  if (!refresh) return false;

  // Сериализуем параллельные попытки рефреша
  if (!refreshing) {
    refreshing = (async () => {
      try {
        const pair = await rawRequest<TokenPairDTO>("/auth/refresh", {
          method: "POST",
          body: { refresh_token: refresh },
        });
        tokenStorage.set(pair);
      } finally {
        // Освободим лок даже при ошибке
        setTimeout(() => {
          refreshing = null;
        }, 0);
      }
    })();
  }

  try {
    await refreshing;
    return !!tokenStorage.access;
  } catch {
    tokenStorage.clear();
    return false;
  }
}

async function request<T>(path: string, opts: RequestOpts = {}): Promise<T> {
  try {
    return await rawRequest<T>(path, opts);
  } catch (err) {
    if (
      err instanceof ApiHttpError &&
      err.status === 401 &&
      opts.auth &&
      path !== "/auth/refresh"
    ) {
      const ok = await tryRefresh();
      if (ok) return rawRequest<T>(path, opts);
    }
    throw err;
  }
}

// ── Public API ────────────────────────────────────────────────────────────────

export const api = {
  auth: {
    register: (email: string, password: string) =>
      request<UserDTO>("/auth/register", {
        method: "POST",
        body: { email, password },
      }),

    verifyEmail: (email: string, code: string) =>
      request<UserDTO>("/auth/verify-email", {
        method: "POST",
        body: { email, code },
      }),

    resendCode: (email: string) =>
      request<MessageDTO>("/auth/resend-code", {
        method: "POST",
        body: { email },
      }),

    login: (email: string, password: string) =>
      request<TokenPairDTO>("/auth/login", {
        method: "POST",
        body: { email, password },
      }),

    me: () => request<UserDTO>("/auth/me", { auth: true }),

    logout: () => request<MessageDTO>("/auth/logout", { method: "POST", auth: true }),
  },

  users: {
    all: () => request<UsersListDTO>("/users/", { auth: true }),
    pending: () => request<UsersListDTO>("/users/pending", { auth: true }),
    activate: (userId: string) =>
      request<UserDTO>(`/users/${userId}/activate`, {
        method: "PATCH",
        auth: true,
      }),
    deactivate: (userId: string) =>
      request<UserDTO>(`/users/${userId}/deactivate`, {
        method: "PATCH",
        auth: true,
      }),
    adminChangePassword: (userId: string, newPassword: string) =>
      request<MessageDTO>("/users/admin/change-password", {
        method: "PATCH",
        body: { user_id: userId, new_password: newPassword },
        auth: true,
      }),
    changeMyPassword: (oldPassword: string, newPassword: string) =>
      request<MessageDTO>("/users/me/password", {
        method: "PATCH",
        body: { old_password: oldPassword, new_password: newPassword },
        auth: true,
      }),
  },

  llm: {
    list: () => request<LLMCredentialsListDTO>("/llm/credentials/", { auth: true }),
    create: (body: {
      provider: "anthropic" | "openai" | "ollama";
      label: string;
      secret: string;
      base_url?: string | null;
      default_model?: string | null;
    }) =>
      request<LLMCredentialDTO>("/llm/credentials/", {
        method: "POST",
        body,
        auth: true,
      }),
    update: (
      id: string,
      body: Partial<{
        label: string;
        secret: string;
        base_url: string | null;
        default_model: string | null;
        is_active: boolean;
      }>,
    ) =>
      request<LLMCredentialDTO>(`/llm/credentials/${id}`, {
        method: "PATCH",
        body,
        auth: true,
      }),
    delete: (id: string) =>
      request<MessageDTO>(`/llm/credentials/${id}`, {
        method: "DELETE",
        auth: true,
      }),
    validate: (id: string) =>
      request<MessageDTO>(`/llm/credentials/${id}/validate`, {
        method: "POST",
        auth: true,
      }),
    models: (id: string) =>
      request<{ models: string[] }>(`/llm/credentials/${id}/models`, {
        auth: true,
      }),
  },

  chats: {
    list: () => request<ChatsListDTO>("/chats/", { auth: true }),
    create: (body: {
      title?: string;
      credential_id?: string | null;
      model?: string | null;
      system_prompt?: string | null;
      agent_mode?: boolean;
    }) =>
      request<ChatDTO>("/chats/", { method: "POST", body, auth: true }),
    get: (id: string) => request<ChatDTO>(`/chats/${id}`, { auth: true }),
    update: (id: string, body: Partial<{ title: string; credential_id: string; model: string; system_prompt: string; agent_mode: boolean }>) =>
      request<ChatDTO>(`/chats/${id}`, { method: "PATCH", body, auth: true }),
    delete: (id: string) =>
      request<MessageDTO>(`/chats/${id}`, { method: "DELETE", auth: true }),
    hide: (id: string) =>
      request<MessageDTO>(`/chats/${id}/hide`, { method: "POST", auth: true }),
    unhide: (id: string) =>
      request<MessageDTO>(`/chats/${id}/unhide`, { method: "POST", auth: true }),
    messages: (id: string) =>
      request<MessagesListDTO>(`/chats/${id}/messages`, { auth: true }),
    switchBranch: (id: string, messageId: string) =>
      request<ChatDTO>(`/chats/${id}/switch-branch`, {
        method: "POST",
        body: { message_id: messageId },
        auth: true,
      }),
    regenerate: (id: string, fromAssistantMessageId: string, branchLabel?: string) =>
      request<ChatMessageDTO>(`/chats/${id}/regenerate`, {
        method: "POST",
        body: { from_assistant_message_id: fromAssistantMessageId, branch_label: branchLabel },
        auth: true,
      }),
    fork: (id: string, fromMessageId: string, newContent: string, branchLabel?: string) =>
      request<ChatMessageDTO>(`/chats/${id}/fork`, {
        method: "POST",
        body: {
          from_message_id: fromMessageId,
          new_content: newContent,
          branch_label: branchLabel,
        },
        auth: true,
      }),
    subtasks: (chatId: string, messageId: string) =>
      request<{
        subtasks: Array<{
          id: string;
          order_index: number;
          title: string;
          status: "pending" | "running" | "done" | "failed";
        }>;
      }>(`/chats/${chatId}/messages/${messageId}/subtasks`, { auth: true }),

    // ── Артефакты ────────────────────────────────────────────────────────
    artifacts: (chatId: string) =>
      request<ArtifactListDTO>(`/chats/${chatId}/artifacts`, { auth: true }),
    artifact: (chatId: string, artifactId: string) =>
      request<ArtifactDetailDTO>(
        `/chats/${chatId}/artifacts/${artifactId}`,
        { auth: true },
      ),
    setArtifactVersion: (chatId: string, artifactId: string, versionId: string) =>
      request<ArtifactDTO>(
        `/chats/${chatId}/artifacts/${artifactId}/set-version`,
        { method: "POST", body: { version_id: versionId }, auth: true },
      ),

    // ── Экспорт ──────────────────────────────────────────────────────────
    exportUrl: (chatId: string, format: "md" | "json"): string => {
      const token = tokenStorage.access;
      // Скачивание идёт прямым navigate'ом — пробросим токен в query
      const u = new URL(`${BASE}/v1/chats/${chatId}/export`, window.location.origin);
      u.searchParams.set("format", format);
      if (token) u.searchParams.set("access_token", token);
      return u.toString();
    },
  },

  files: {
    parse: async (file: File): Promise<ParsedFileDTO> => {
      const fd = new FormData();
      fd.append("file", file);
      const token = tokenStorage.access;
      const resp = await fetch(`${BASE}/v1/chats/parse-file`, {
        method: "POST",
        body: fd,
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!resp.ok) {
        const payload = await resp.json().catch(() => null);
        throw new ApiHttpError(
          resp.status,
          payload?.code ?? resp.status,
          payload?.detail ?? `HTTP ${resp.status}`,
        );
      }
      return resp.json();
    },
  },

  prompts: {
    list: () => request<SystemPromptListDTO>("/system-prompts/", { auth: true }),
    create: (body: {
      title: string;
      content: string;
      description?: string | null;
      icon?: string | null;
    }) =>
      request<SystemPromptDTO>("/system-prompts/", {
        method: "POST",
        body,
        auth: true,
      }),
    update: (
      id: string,
      body: Partial<{
        title: string;
        content: string;
        description: string | null;
        icon: string | null;
        is_pinned: boolean;
      }>,
    ) =>
      request<SystemPromptDTO>(`/system-prompts/${id}`, {
        method: "PATCH",
        body,
        auth: true,
      }),
    delete: (id: string) =>
      request<MessageDTO>(`/system-prompts/${id}`, {
        method: "DELETE",
        auth: true,
      }),
  },

  sandbox: {
    getOrCreate: (chatId: string) =>
      request<SandboxDTO>(`/chats/${chatId}/sandbox`, { auth: true }),
    remove: (chatId: string) =>
      request<MessageDTO>(`/chats/${chatId}/sandbox`, {
        method: "DELETE",
        auth: true,
      }),
    listFiles: (chatId: string, subdir = "") =>
      request<{ files: FileEntryDTO[]; workspace: string }>(
        `/chats/${chatId}/files/?subdir=${encodeURIComponent(subdir)}`,
        { auth: true },
      ),
    downloadFileUrl: (chatId: string, path: string): string => {
      const token = tokenStorage.access;
      const u = new URL(
        `${BASE}/v1/chats/${chatId}/files/download`,
        window.location.origin,
      );
      u.searchParams.set("path", path);
      if (token) u.searchParams.set("access_token", token);
      return u.toString();
    },
    zipUrl: (chatId: string): string => {
      const token = tokenStorage.access;
      const u = new URL(
        `${BASE}/v1/chats/${chatId}/files.zip`,
        window.location.origin,
      );
      if (token) u.searchParams.set("access_token", token);
      return u.toString();
    },

    adminList: () =>
      request<{
        sandboxes: Array<{
          id: string;
          chat_id: string;
          user_id: string;
          container_id: string | null;
          container_name: string;
          image: string;
          status_db: string;
          status_live: string | null;
          workspace_path: string;
          last_used_at: string | null;
          error: string | null;
        }>;
        total: number;
      }>("/admin/sandboxes/", { auth: true }),
    adminExec: (sandboxId: string, command: string, timeout = 60) =>
      request<{ exit_code: number; stdout: string; stderr: string }>(
        `/admin/sandboxes/${sandboxId}/exec`,
        { method: "POST", body: { command, timeout }, auth: true },
      ),
    adminRemove: (sandboxId: string) =>
      request<MessageDTO>(`/admin/sandboxes/${sandboxId}`, {
        method: "DELETE",
        auth: true,
      }),
  },

  mcp: {
    list: () =>
      request<{ servers: MCPServerDTO[]; total: number }>("/mcp-servers/", {
        auth: true,
      }),
    create: (body: {
      name: string;
      description?: string | null;
      transport: "sse" | "http" | "stdio";
      url?: string | null;
      command?: Record<string, any> | null;
      config?: Record<string, any> | null;
    }) =>
      request<MCPServerDTO>("/mcp-servers/", {
        method: "POST",
        body,
        auth: true,
      }),
    update: (id: string, body: Partial<{
      name: string;
      description: string | null;
      transport: "sse" | "http" | "stdio";
      url: string | null;
      command: Record<string, any> | null;
      config: Record<string, any> | null;
      is_enabled: boolean;
    }>) =>
      request<MCPServerDTO>(`/mcp-servers/${id}`, {
        method: "PATCH",
        body,
        auth: true,
      }),
    delete: (id: string) =>
      request<MessageDTO>(`/mcp-servers/${id}`, {
        method: "DELETE",
        auth: true,
      }),
    validate: (id: string) =>
      request<{ tools: Array<{ name: string; description: string; input_schema: any }> }>(
        `/mcp-servers/${id}/validate`,
        { method: "POST", auth: true },
      ),
  },
};

export { ApiHttpError };
