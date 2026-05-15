"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { ToolCallDTO } from "@/lib/chat-types";
import styles from "./ToolCallBlock.module.css";

interface Props {
  call: ToolCallDTO;
  chatId: string;
}

/**
 * Один блок tool-call в сообщении ассистента.
 *
 * Рендерится свёрнутым: «🔧 bash · running…» / «✓ bash · done».
 * Клик — разворачивается с input (JSON параметры) и output (текст ответа).
 *
 * Специальный случай: `present_files` — рендерится отдельно как «📦 Файлы»
 * со списком файлов и кнопкой скачать (см. parsePresentFiles).
 */
export function ToolCallBlock({ call, chatId }: Props) {
  const [expanded, setExpanded] = useState(false);

  // present_files имеет особый формат вывода — распарсим
  if (call.is_present_files && call.output) {
    return <PresentFilesBlock output={call.output} chatId={chatId} />;
  }

  const statusIcon =
    call.status === "running" ? "⌗" : call.status === "error" ? "⌗" : "⌗";
  const statusColor =
    call.status === "running"
      ? "var(--yellow)"
      : call.status === "error"
        ? "var(--red)"
        : "var(--muted)";

  // Имя tool с префиксом mcp__<uuid>__ → показываем без префикса
  const displayName = call.name.startsWith("mcp__")
    ? call.name.split("__").slice(2).join("__") + " (mcp)"
    : call.name;

  return (
    <div className={styles.block}>
      <button
        className={styles.header}
        onClick={() => setExpanded((v) => !v)}
        type="button"
      >
        <span className={styles.icon} style={{ color: statusColor }}>
          {statusIcon}
        </span>
        <span className={styles.toolName}>{displayName}</span>
        {briefInput(call.input) && (
          <span className={styles.toolBrief}>· {briefInput(call.input)}</span>
        )}
        <span className={styles.chev}>{expanded ? "▾" : "▸"}</span>
      </button>

      {expanded && (
        <div className={styles.body}>
          <div className={styles.sectionLabel}>// input</div>
          <pre className={styles.pre}>{JSON.stringify(call.input, null, 2)}</pre>
          {call.output !== undefined && (
            <>
              <div className={styles.sectionLabel}>// output</div>
              <pre className={styles.pre}>{call.output}</pre>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function briefInput(input: Record<string, any>): string {
  // Покажем первое непустое значение коротко
  for (const k of Object.keys(input)) {
    const v = input[k];
    if (typeof v === "string" && v) {
      return v.length > 60 ? v.slice(0, 60) + "…" : v;
    }
  }
  return "";
}

// ── present_files ──────────────────────────────────────────────────────────

function PresentFilesBlock({ output, chatId }: { output: string; chatId: string }) {
  const parsed = parsePresentFiles(output);

  // Защита от пустого списка — на бэке мы это уже отсекаем как ERROR,
  // но если протокол поменяется или будет race — покажем понятный текст.
  if (parsed.files.length === 0) {
    return (
      <div className={styles.filesBlock}>
        <div className={styles.filesHeader}>
          <span className={styles.filesIcon}>⚠</span>
          <span className={styles.filesTitle}>
            {parsed.caption || "Файлы"}: ничего не найдено
          </span>
        </div>
        <div style={{ fontSize: 11, color: "var(--dim)", fontFamily: "var(--mono)" }}>
          // пути не найдены в workspace
        </div>
      </div>
    );
  }

  const singleFile = parsed.files.length === 1 ? parsed.files[0] : null;

  return (
    <div className={styles.filesBlock}>
      <div className={styles.filesHeader}>
        <span className={styles.filesIcon}>📦</span>
        {/* Если файл один — заголовок сам кликабельный, ведёт на скачку */}
        {singleFile ? (
          <a
            className={styles.filesTitleLink}
            href={api.sandbox.downloadFileUrl(chatId, singleFile.path)}
            download
          >
            {parsed.caption || singleFile.path}
            <span className={styles.filesSizeBadge}>
              {formatBytes(singleFile.size)}
            </span>
          </a>
        ) : (
          <span className={styles.filesTitle}>
            {parsed.caption || `${parsed.files.length} файлов`}
          </span>
        )}
        <span style={{ flex: 1 }} />
        {parsed.files.length > 1 && (
          <a
            className={styles.filesAllBtn}
            href={api.sandbox.zipUrl(chatId)}
            download
          >
            всё в zip
          </a>
        )}
      </div>
      {!singleFile && (
        <ul className={styles.filesList}>
          {parsed.files.map((f) => (
            <li key={f.path} className={styles.fileItem}>
              <a
                className={styles.fileLink}
                href={api.sandbox.downloadFileUrl(chatId, f.path)}
                download
              >
                <span className={styles.filePath}>{f.path}</span>
                <span className={styles.fileSize}>{formatBytes(f.size)}</span>
                <span className={styles.fileDl}>↓</span>
              </a>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function parsePresentFiles(output: string): {
  caption: string;
  files: Array<{ path: string; size: number }>;
} {
  const lines = output.split("\n");
  // первая строка — маркер; вторая — caption; дальше path\tsize
  const caption = (lines[1] || "").trim();
  const files: Array<{ path: string; size: number }> = [];
  for (const line of lines.slice(2)) {
    if (!line.trim()) continue;
    if (line.startsWith("WARNING:")) continue;
    const [path, sizeStr] = line.split("\t");
    if (path && sizeStr) {
      files.push({ path: path.trim(), size: parseInt(sizeStr, 10) || 0 });
    }
  }
  return { caption, files };
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
