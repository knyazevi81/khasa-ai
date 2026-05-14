"use client";

import { create } from "zustand";
import { api } from "./api";
import { tokenStorage } from "./token-storage";
import type {
  ArtifactPushDTO,
  ChatDTO,
  MessageDTO,
  WSIncoming,
  WSOutgoing,
} from "./chat-types";

interface ChatState {
  chat: ChatDTO | null;
  messages: MessageDTO[];          // все узлы графа (плоский список)
  currentMessageId: string | null;
  streaming: boolean;
  error: string | null;

  ws: WebSocket | null;

  // Последний «push» обновления артефакта от сервера — фронт ArtifactPanel
  // подписан на это поле и сам перечитывает деталь.
  lastArtifactPush: ArtifactPushDTO | null;

  // actions
  loadChat: (id: string) => Promise<void>;
  connect: (chatId: string) => void;
  disconnect: () => void;
  sendMessage: (content: string, parentId?: string | null) => void;
  regenerate: (fromAssistantMessageId: string) => void;
  forkMessage: (fromMessageId: string, newContent: string) => void;
  switchToBranch: (messageId: string) => Promise<void>;
  reloadMessages: () => Promise<void>;
}

export const useChatStore = create<ChatState>((set, get) => ({
  chat: null,
  messages: [],
  currentMessageId: null,
  streaming: false,
  error: null,
  ws: null,
  lastArtifactPush: null,

  loadChat: async (id) => {
    const [chat, msgList] = await Promise.all([
      api.chats.get(id),
      api.chats.messages(id),
    ]);
    set({
      chat,
      messages: msgList.messages,
      currentMessageId: msgList.current_message_id,
      error: null,
    });
  },

  reloadMessages: async () => {
    const chat = get().chat;
    if (!chat) return;
    const msgList = await api.chats.messages(chat.id);
    set({
      messages: msgList.messages,
      currentMessageId: msgList.current_message_id,
    });
  },

  connect: (chatId) => {
    if (get().ws) return; // уже подключены
    const token = tokenStorage.access;
    if (!token) {
      set({ error: "Не авторизован" });
      return;
    }

    // ws:// vs wss:// по протоколу страницы
    const proto = typeof window !== "undefined" && window.location.protocol === "https:"
      ? "wss:"
      : "ws:";
    const host = typeof window !== "undefined" ? window.location.host : "localhost";
    const url = `${proto}//${host}/api/v1/chats/${chatId}/stream?token=${encodeURIComponent(token)}`;

    const ws = new WebSocket(url);

    ws.onopen = () => {
      set({ ws, error: null });
    };

    ws.onmessage = (ev) => {
      let payload: WSIncoming;
      try {
        payload = JSON.parse(ev.data);
      } catch {
        return;
      }
      handleIncoming(payload, set, get);
    };

    ws.onerror = () => {
      set({ error: "WebSocket: соединение прервано", streaming: false });
    };

    ws.onclose = () => {
      set({ ws: null, streaming: false });
    };
  },

  disconnect: () => {
    const ws = get().ws;
    if (ws) ws.close();
    set({ ws: null });
  },

  sendMessage: (content, parentId) => {
    const ws = get().ws;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      set({ error: "Нет соединения с сервером" });
      return;
    }
    const payload: WSOutgoing = {
      type: "send",
      content,
      parent_id: parentId ?? null,
    };
    ws.send(JSON.stringify(payload));
    set({ streaming: true, error: null });
  },

  regenerate: (fromAssistantMessageId) => {
    const ws = get().ws;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      set({ error: "Нет соединения" });
      return;
    }
    const payload: WSOutgoing = {
      type: "regenerate",
      from_assistant_message_id: fromAssistantMessageId,
    };
    ws.send(JSON.stringify(payload));
    set({ streaming: true, error: null });
  },

  forkMessage: (fromMessageId, newContent) => {
    const ws = get().ws;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      set({ error: "Нет соединения" });
      return;
    }
    const payload: WSOutgoing = {
      type: "fork",
      from_message_id: fromMessageId,
      new_content: newContent,
    };
    ws.send(JSON.stringify(payload));
    set({ streaming: true, error: null });
  },

  switchToBranch: async (messageId) => {
    const chat = get().chat;
    if (!chat) return;
    await api.chats.switchBranch(chat.id, messageId);
    set({ currentMessageId: messageId });
  },
}));


function handleIncoming(
  payload: WSIncoming,
  set: (partial: Partial<ChatState> | ((s: ChatState) => Partial<ChatState>)) => void,
  get: () => ChatState,
): void {
  switch (payload.type) {
    case "user_message_created": {
      const msg = payload.message;
      set((s) => {
        const existing = s.messages.find((m) => m.id === msg.id);
        const messages = existing
          ? s.messages.map((m) => (m.id === msg.id ? msg : m))
          : [...s.messages, msg];
        return {
          messages,
          currentMessageId: msg.id,
        };
      });
      // Бэк мог переименовать чат (автотайтлинг) — подтянем заголовок
      const chat = get().chat;
      if (chat && (chat.title === "Новый чат" || chat.title === "")) {
        api.chats.get(chat.id).then((c) => set({ chat: c })).catch(() => {});
      }
      break;
    }

    case "assistant_message_created": {
      const msg = payload.message;
      set((s) => {
        const existing = s.messages.find((m) => m.id === msg.id);
        const messages = existing
          ? s.messages.map((m) => (m.id === msg.id ? msg : m))
          : [...s.messages, msg];
        return {
          messages,
          currentMessageId: msg.id,
        };
      });
      break;
    }

    case "delta": {
      set((s) => ({
        messages: s.messages.map((m) =>
          m.id === payload.message_id
            ? { ...m, content: m.content + payload.text, status: "streaming" }
            : m,
        ),
      }));
      break;
    }

    case "done": {
      set((s) => ({
        streaming: false,
        messages: s.messages.map((m) =>
          m.id === payload.message_id
            ? {
                ...m,
                status: "ready",
                input_tokens: payload.usage?.input_tokens ?? m.input_tokens,
                output_tokens: payload.usage?.output_tokens ?? m.output_tokens,
              }
            : m,
        ),
      }));
      break;
    }

    case "error": {
      set((s) => ({
        streaming: false,
        error: payload.error,
        messages: payload.message_id
          ? s.messages.map((m) =>
              m.id === payload.message_id
                ? { ...m, status: "failed", error: payload.error }
                : m,
            )
          : s.messages,
      }));
      break;
    }

    case "artifact": {
      set({ lastArtifactPush: payload.artifact });
      break;
    }
  }
}
