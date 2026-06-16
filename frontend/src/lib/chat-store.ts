"use client";

import { create } from "zustand";
import { api } from "./api";
import { tokenStorage } from "./token-storage";
import type {
  ArtifactPushDTO,
  ChatDTO,
  MessageDTO,
  MessageSegment,
  ToolCallDTO,
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

  // Сегменты ассистент-сообщений (text + tool_call в порядке появления).
  // При стриме обновляются по WS, при reload — подтягиваются из /segments.
  // Старый `toolCallsByMessage` остаётся для совместимости.
  toolCallsByMessage: Record<string, ToolCallDTO[]>;
  segmentsByMessage: Record<string, MessageSegment[]>;

  // Сообщения которые упёрлись в AGENT_MAX_TURNS — фронт показывает у них
  // кнопку «продолжить» (отправляет новый user-msg «продолжай» и стримит
  // дальше). Очищается при disconnect.
  truncatedMessages: Set<string>;

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
  toolCallsByMessage: {},
  segmentsByMessage: {},
  truncatedMessages: new Set(),

  loadChat: async (id) => {
    const [chat, msgList, toolCallsRes, segmentsRes] = await Promise.all([
      api.chats.get(id),
      api.chats.messages(id),
      api.chats.toolCalls(id).catch(() => ({ tool_calls: {} as Record<string, ToolCallDTO[]> })),
      api.chats.segments(id).catch(() => ({ segments: {} as Record<string, MessageSegment[]> })),
    ]);
    set({
      chat,
      messages: msgList.messages,
      currentMessageId: msgList.current_message_id,
      toolCallsByMessage: toolCallsRes.tool_calls as Record<string, ToolCallDTO[]>,
      segmentsByMessage: segmentsRes.segments as Record<string, MessageSegment[]>,
      error: null,
    });
  },

  reloadMessages: async () => {
    const chat = get().chat;
    if (!chat) return;
    const [msgList, toolCallsRes, segmentsRes] = await Promise.all([
      api.chats.messages(chat.id),
      api.chats.toolCalls(chat.id).catch(() => ({ tool_calls: {} as Record<string, ToolCallDTO[]> })),
      api.chats.segments(chat.id).catch(() => ({ segments: {} as Record<string, MessageSegment[]> })),
    ]);
    set({
      messages: msgList.messages,
      currentMessageId: msgList.current_message_id,
      toolCallsByMessage: toolCallsRes.tool_calls as Record<string, ToolCallDTO[]>,
      segmentsByMessage: segmentsRes.segments as Record<string, MessageSegment[]>,
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
    // Сбрасываем артефакт-push и tool-calls — при возврате в чат они подтянутся
    // заново через ArtifactPanel/WS, а старое состояние не должно остаться.
    set({
      ws: null,
      lastArtifactPush: null,
      // Не сбрасываем toolCallsByMessage — они теперь персистятся в БД и
      // подтянутся при следующем loadChat (или останутся актуальными если
      // юзер просто закрыл вкладку с тем же чатом).
      truncatedMessages: new Set(),
    });
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
      // В агент-режиме delta приходит с segment_id и order_idx — пишем в
      // нужный сегмент. Это даёт interleaved-рендер «text → tool → text».
      // В обычном режиме segment_id отсутствует — пишем в m.content по-старому.
      if (payload.segment_id) {
        const segId = payload.segment_id;
        const order = payload.order_idx ?? 0;
        // Спец-режим: бэк прислал replace=true с готовым контентом —
        // это значит мы вырезали JSON-план или сделали другую правку.
        // Фронт переписывает текст сегмента полностью.
        const isReplace = (payload as any).replace === true;
        const replaceContent = (payload as any).content as string | undefined;
        set((s) => {
          const msgId = payload.message_id;
          const list = s.segmentsByMessage[msgId] || [];
          const existing = list.find(
            (seg) => seg.kind === "text" && seg.id === segId,
          );
          let next: MessageSegment[];
          if (existing && existing.kind === "text") {
            next = list.map((seg) =>
              seg.kind === "text" && seg.id === segId
                ? {
                    ...seg,
                    content: isReplace
                      ? replaceContent ?? ""
                      : seg.content + payload.text,
                  }
                : seg,
            );
          } else {
            next = [
              ...list,
              {
                kind: "text" as const,
                order_idx: order,
                id: segId,
                content: isReplace ? replaceContent ?? "" : payload.text,
              },
            ];
            next.sort((a, b) => a.order_idx - b.order_idx);
          }
          return {
            segmentsByMessage: { ...s.segmentsByMessage, [msgId]: next },
            messages: s.messages.map((m) =>
              m.id === msgId ? { ...m, status: "streaming" } : m,
            ),
          };
        });
      } else {
        // legacy / non-agent режим
        set((s) => ({
          messages: s.messages.map((m) =>
            m.id === payload.message_id
              ? { ...m, content: m.content + payload.text, status: "streaming" }
              : m,
          ),
        }));
      }
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

    case "tool_use": {
      const msgId = get().currentMessageId;
      if (!msgId) break;
      const order = payload.order_idx ?? 0;
      set((s) => {
        // 1) Старый toolCallsByMessage — для обратной совместимости
        const list = s.toolCallsByMessage[msgId] || [];
        const existing = list.find((c) => c.id === payload.id);
        const status = (payload.status as ToolCallDTO["status"]) || "running";
        const nextCalls: ToolCallDTO[] = existing
          ? list.map((c) => (c.id === payload.id ? { ...c, status } : c))
          : [
              ...list,
              {
                id: payload.id,
                name: payload.name,
                input: payload.input,
                status,
              },
            ];

        // 2) segmentsByMessage — апсёрт tool_call сегмента
        const segList = s.segmentsByMessage[msgId] || [];
        const existingSeg = segList.find(
          (seg) => seg.kind === "tool_call" && seg.id === payload.id,
        );
        let nextSegs: MessageSegment[];
        if (existingSeg) {
          nextSegs = segList.map((seg) =>
            seg.kind === "tool_call" && seg.id === payload.id
              ? { ...seg, status }
              : seg,
          );
        } else {
          nextSegs = [
            ...segList,
            {
              kind: "tool_call" as const,
              order_idx: order,
              id: payload.id,
              name: payload.name,
              input: payload.input,
              output: null,
              status,
              is_present_files: false,
            },
          ];
          nextSegs.sort((a, b) => a.order_idx - b.order_idx);
        }

        return {
          toolCallsByMessage: { ...s.toolCallsByMessage, [msgId]: nextCalls },
          segmentsByMessage: { ...s.segmentsByMessage, [msgId]: nextSegs },
        };
      });
      break;
    }

    case "tool_result": {
      const msgId = get().currentMessageId;
      if (!msgId) break;
      set((s) => {
        // Старый toolCallsByMessage
        const list = s.toolCallsByMessage[msgId] || [];
        const nextCalls = list.map((c) =>
          c.id === payload.id
            ? {
                ...c,
                status: "done" as const,
                output: payload.output,
                is_present_files: payload.is_present_files,
              }
            : c,
        );
        // segmentsByMessage — обновляем сегмент tool_call
        const segList = s.segmentsByMessage[msgId] || [];
        const nextSegs: MessageSegment[] = segList.map((seg) =>
          seg.kind === "tool_call" && seg.id === payload.id
            ? {
                ...seg,
                output: payload.output,
                status: "done" as const,
                is_present_files: payload.is_present_files ?? false,
              }
            : seg,
        );
        return {
          toolCallsByMessage: { ...s.toolCallsByMessage, [msgId]: nextCalls },
          segmentsByMessage: { ...s.segmentsByMessage, [msgId]: nextSegs },
        };
      });
      break;
    }

    case "truncated": {
      set((s) => {
        const next = new Set(s.truncatedMessages);
        next.add(payload.message_id);
        return { truncatedMessages: next };
      });
      break;
    }
  }
}
