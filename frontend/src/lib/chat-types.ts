// Типы, отвечающие схемам бэкенда (app/presentation/fastapi/schemas/chat.py)

export interface ChatDTO {
  id: string;
  title: string;
  current_message_id: string | null;
  credential_id: string | null;
  model: string | null;
  system_prompt: string | null;
  agent_mode: boolean;
}

export interface ChatsListDTO {
  chats: ChatDTO[];
  total: number;
}

export interface MessageDTO {
  id: string;
  chat_id: string;
  parent_id: string | null;
  role: "user" | "assistant" | "system";
  content: string;
  branch_label: string | null;
  status: "pending" | "streaming" | "ready" | "failed";
  provider: string | null;
  model: string | null;
  input_tokens: number;
  output_tokens: number;
  error: string | null;
}

export interface MessagesListDTO {
  messages: MessageDTO[];
  current_message_id: string | null;
}

export interface LLMCredentialDTO {
  id: string;
  provider: "anthropic" | "openai" | "ollama";
  label: string;
  secret_mask: string;
  base_url: string | null;
  default_model: string | null;
  is_active: boolean;
}

export interface LLMCredentialsListDTO {
  credentials: LLMCredentialDTO[];
  total: number;
}

export interface ParsedFileDTO {
  filename: string;
  kind: "txt" | "pdf";
  size_bytes: number;
  extracted_text: string;
  extracted_chars: number;
}

// ── События WebSocket ────────────────────────────────────────────────────────

export type WSIncoming =
  | { type: "user_message_created"; message: MessageDTO }
  | { type: "assistant_message_created"; message: MessageDTO }
  | { type: "delta"; message_id: string; text: string; segment_id?: string | null; order_idx?: number }
  | { type: "done"; message_id: string; usage?: { input_tokens: number; output_tokens: number } }
  | { type: "error"; message_id?: string; error: string }
  | { type: "artifact"; artifact: ArtifactPushDTO }
  | { type: "tool_use"; id: string; name: string; input: Record<string, any>; status?: "running" | "done" | "error"; order_idx?: number }
  | { type: "tool_result"; id: string; name: string; output: string; is_present_files?: boolean; order_idx?: number }
  | { type: "truncated"; reason: string; max_turns: number; message_id: string };

export type WSOutgoing =
  | { type: "send"; content: string; parent_id?: string | null }
  | { type: "regenerate"; from_assistant_message_id: string; branch_label?: string }
  | { type: "fork"; from_message_id: string; new_content: string; branch_label?: string };

// ── Артефакты ────────────────────────────────────────────────────────────────

export interface ArtifactDTO {
  id: string;
  chat_id: string;
  slug: string;
  kind: "markdown" | "code" | "html" | "svg" | "mermaid" | "json";
  title: string;
  language: string | null;
  current_version_id: string | null;
}

export interface ArtifactVersionDTO {
  id: string;
  artifact_id: string;
  version_no: number;
  content: string;
  message_id: string;
}

export interface ArtifactListDTO {
  artifacts: ArtifactDTO[];
  total: number;
}

export interface ArtifactDetailDTO {
  artifact: ArtifactDTO;
  versions: ArtifactVersionDTO[];
}

// WS-событие создания/обновления артефакта
export interface ArtifactPushDTO {
  artifact_id: string;
  version_id: string;
  slug: string;
  kind: ArtifactDTO["kind"];
  title: string;
  language: string | null;
}

// ── Системные промпты ───────────────────────────────────────────────────────

export interface SystemPromptDTO {
  id: string;
  title: string;
  content: string;
  description: string | null;
  icon: string | null;
  is_pinned: boolean;
}

export interface SystemPromptListDTO {
  prompts: SystemPromptDTO[];
  total: number;
}

// ── Tool calls (agent mode) ─────────────────────────────────────────────────

export interface ToolCallDTO {
  id: string;
  name: string;
  input: Record<string, any>;
  status: "running" | "done" | "error";
  output?: string;
  is_present_files?: boolean;
}

// ── Sandbox / files ─────────────────────────────────────────────────────────

export interface SandboxDTO {
  id: string;
  chat_id: string;
  user_id: string;
  container_id: string | null;
  container_name: string;
  image: string;
  status: string;
  workspace_path: string;
  last_used_at: string | null;
  error: string | null;
}

export interface FileEntryDTO {
  path: string;
  is_dir: boolean;
  size: number;
  modified_at: number;
}

// ── MCP ─────────────────────────────────────────────────────────────────────

export interface MCPServerDTO {
  id: string;
  name: string;
  description: string | null;
  transport: "sse" | "http" | "stdio";
  url: string | null;
  command: Record<string, any> | null;
  config: Record<string, any> | null;
  is_enabled: boolean;
  tools_cache: { tools?: Array<{ name: string; description: string; input_schema?: any }> } | null;
}

// ── Message segments (interleaved text + tools) ─────────────────────────────

export type MessageSegment =
  | { kind: "text"; order_idx: number; id: string; content: string }
  | {
      kind: "tool_call";
      order_idx: number;
      id: string;
      name: string;
      input: Record<string, any>;
      output: string | null;
      status: "running" | "done" | "error";
      is_present_files: boolean;
    };
