"use client";

import { useMemo } from "react";
import type { MessageDTO } from "@/lib/chat-types";
import { layoutGraph } from "@/lib/graph-layout";
import styles from "./GraphView.module.css";

interface Props {
  messages: MessageDTO[];
  currentMessageId: string | null;
  onNodeClick?: (messageId: string) => void;
  onNodeContextMenu?: (e: React.MouseEvent, messageId: string) => void;
  /** Если true — рендер компактнее (миниатюра в углу) */
  compact?: boolean;
  /** Если true — не показывать легенду и подписи (для миниатюры) */
  minimal?: boolean;
}

/**
 * SVG-граф диалога, стилизованный под `khasa-dark.jsx`:
 *   • кривые Безье между узлами (мягкие S-образные изгибы)
 *   • main = solid + цвет текста, alt-* = пунктир + бренд-цвет
 *   • активный узел — кольцо вокруг с opacity 0.4 + метка NOW внутри
 *   • подпись узла справа (только не в minimal-режиме)
 *   • сетка на фоне для глубины
 *
 * Юзер-узел = квадрат, ассистент = круг.
 */
export function GraphView({
  messages,
  currentMessageId,
  onNodeClick,
  onNodeContextMenu,
  compact = false,
  minimal = false,
}: Props) {
  const layout = useMemo(
    () => layoutGraph(messages, currentMessageId),
    [messages, currentMessageId],
  );

  if (messages.length === 0) {
    return (
      <div className={styles.wrap}>
        <div className={styles.empty}>// граф пуст — начните диалог</div>
      </div>
    );
  }

  const width = Math.max(layout.width, compact ? 280 : 600);
  const height = Math.max(layout.height + 30, compact ? 220 : 400);
  const nodeRadius = compact ? 6 : 11;
  const ringRadius = nodeRadius + (compact ? 5 : 8);

  return (
    <div className={styles.wrap}>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className={styles.svg}
        preserveAspectRatio="xMidYMid meet"
      >
        <defs>
          <pattern
            id="grid-d"
            width={compact ? 16 : 32}
            height={compact ? 16 : 32}
            patternUnits="userSpaceOnUse"
          >
            <path
              d={`M ${compact ? 16 : 32} 0 L 0 0 0 ${compact ? 16 : 32}`}
              fill="none"
              stroke="rgba(255,255,255,0.03)"
              strokeWidth="1"
            />
          </pattern>
        </defs>
        <rect width={width} height={height} fill="url(#grid-d)" />

        {/* Рёбра (кривые Безье) */}
        {layout.edges.map((e) => {
          const from = layout.nodes.find((n) => n.id === e.fromId);
          const to = layout.nodes.find((n) => n.id === e.toId);
          if (!from || !to) return null;
          const isMain = to.branchIndex === 0;
          const stroke = to.branchColor;
          // S-образная кривая через две контрольные точки
          const mx = (from.x + to.x) / 2;
          return (
            <path
              key={`${e.fromId}-${e.toId}`}
              d={`M ${from.x} ${from.y} C ${mx} ${from.y}, ${mx} ${to.y}, ${to.x} ${to.y}`}
              stroke={stroke}
              strokeWidth={isMain ? 2 : 1.5}
              strokeDasharray={isMain ? undefined : "4 4"}
              fill="none"
              opacity={isMain ? 0.9 : 0.7}
            />
          );
        })}

        {/* Узлы */}
        {layout.nodes.map((n) => {
          const isActive = n.id === currentMessageId;
          const isUser = n.role === "user";
          const isMain = n.branchIndex === 0;
          const stroke = n.branchColor;
          const fill = isActive
            ? stroke
            : isMain
              ? "var(--surf)"
              : "transparent";
          const r = isActive ? nodeRadius + 5 : nodeRadius;
          const labelText = labelFor(messages, n.id);
          const labelDisplay = truncate(labelText, compact ? 12 : 18);
          const labelWidth = Math.max(40, labelDisplay.length * (compact ? 5.5 : 6.5) + 10);

          return (
            <g
              key={n.id}
              className={styles.node}
              transform={`translate(${n.x}, ${n.y})`}
              onClick={() => onNodeClick?.(n.id)}
              onContextMenu={(e) => onNodeContextMenu?.(e, n.id)}
              style={{ opacity: n.status === "pending" ? 0.5 : 1 }}
            >
              {/* Кольцо вокруг активного */}
              {isActive && (
                <circle
                  r={ringRadius}
                  fill="none"
                  stroke={stroke}
                  strokeWidth={1.5}
                  opacity={0.4}
                />
              )}

              {isUser ? (
                <rect
                  x={-r}
                  y={-r}
                  width={r * 2}
                  height={r * 2}
                  rx={1}
                  fill={fill}
                  stroke={stroke}
                  strokeWidth={1.5}
                />
              ) : (
                <circle
                  r={r}
                  fill={fill}
                  stroke={stroke}
                  strokeWidth={2}
                />
              )}

              {isActive && !compact && (
                <text
                  textAnchor="middle"
                  dy={4}
                  fill="var(--bg)"
                  fontFamily="var(--mono)"
                  fontSize={9}
                  fontWeight={700}
                  style={{ pointerEvents: "none" }}
                >
                  NOW
                </text>
              )}

              {/* Стрим-индикатор */}
              {n.status === "streaming" && (
                <circle
                  cx={r + 4}
                  cy={-r - 2}
                  r={2.5}
                  fill="var(--yellow)"
                >
                  <animate
                    attributeName="opacity"
                    values="0.3;1;0.3"
                    dur="1s"
                    repeatCount="indefinite"
                  />
                </circle>
              )}

              {/* Подпись под узлом — небольшая, с подложкой чтобы не сливаться */}
              {!minimal && labelText && (
                <g style={{ pointerEvents: "none" }}>
                  <rect
                    x={-labelWidth / 2}
                    y={r + 6}
                    width={labelWidth}
                    height={16}
                    rx={3}
                    fill="var(--bg)"
                    stroke="var(--rule)"
                    strokeWidth={1}
                    opacity={0.92}
                  />
                  <text
                    x={0}
                    y={r + 17}
                    textAnchor="middle"
                    fill="var(--text)"
                    fontFamily="var(--mono)"
                    fontSize={compact ? 9 : 10}
                  >
                    {labelDisplay}
                  </text>
                </g>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

// ── helpers ──────────────────────────────────────────────────────────────────

function labelFor(messages: MessageDTO[], id: string): string {
  const m = messages.find((x) => x.id === id);
  if (!m) return "";
  const text = (m.content || "").replace(/```[\s\S]*?```/g, "").trim();
  if (!text) {
    return m.role === "assistant" ? "[стрим]" : "[пусто]";
  }
  return text.split("\n")[0].slice(0, 60);
}

function truncate(s: string, n: number): string {
  return s.length <= n ? s : s.slice(0, n - 1) + "…";
}
