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
}

/**
 * SVG-граф диалога. Узлы — кружки разного типа в зависимости от role:
 *   user      = квадрат
 *   assistant = круг
 *   system    = ромб
 * Цвет берётся из «полосы ветки» (см. graph-layout.ts).
 * Активный узел (current_message_id) обведён большим контуром.
 *
 * Левый клик по узлу — switch активной ветки.
 * Правый клик по узлу — открыть форк (новое user-сообщение от этого узла).
 */
export function GraphView({
  messages,
  currentMessageId,
  onNodeClick,
  onNodeContextMenu,
}: Props) {
  const layout = useMemo(
    () => layoutGraph(messages, currentMessageId),
    [messages, currentMessageId],
  );

  if (messages.length === 0) {
    return (
      <div className={styles.wrap}>
        <div className={styles.empty}>
          // граф пуст — начните диалог
        </div>
      </div>
    );
  }

  return (
    <div className={styles.wrap}>
      <div className={styles.legend}>
        <span>// граф диалога</span>
        <span className={styles.item}>
          <span className={styles.swatch} style={{ background: "var(--green)" }} />
          main
        </span>
        <span className={styles.item}>
          <span className={styles.swatch} style={{ background: "var(--yellow)" }} />
          alt
        </span>
        <span className={styles.item}>
          <span className={styles.swatch} style={{ background: "var(--red)" }} />
          alt
        </span>
      </div>

      <div
        className={styles.canvas}
        style={{
          width: Math.max(layout.width, 600),
          height: Math.max(layout.height, 400),
        }}
      >
        <svg
          className={styles.svg}
          width={Math.max(layout.width, 600)}
          height={Math.max(layout.height, 400)}
        >
          {/* Рёбра */}
          {layout.edges.map((e) => {
            const from = layout.nodes.find((n) => n.id === e.fromId);
            const to = layout.nodes.find((n) => n.id === e.toId);
            if (!from || !to) return null;
            return (
              <line
                key={`${e.fromId}-${e.toId}`}
                x1={from.x}
                y1={from.y}
                x2={to.x}
                y2={to.y}
                stroke={to.branchColor}
                strokeOpacity={0.35}
                strokeWidth={1.5}
              />
            );
          })}

          {/* Узлы */}
          {layout.nodes.map((n) => {
            const isActive = n.id === currentMessageId;
            const stroke = n.branchColor;
            const fill =
              n.role === "user" ? "var(--surf)" : isActive ? n.branchColor : "var(--bg)";
            const textColor = n.role === "user" || isActive ? "#fff" : n.branchColor;

            const dim =
              n.status === "pending" || n.status === "streaming" ? 0.7 : 1;

            return (
              <g
                key={n.id}
                className={styles.node}
                onClick={() => onNodeClick?.(n.id)}
                onContextMenu={(e) => onNodeContextMenu?.(e, n.id)}
                style={{ opacity: dim }}
              >
                {/* Активный узел — внешнее кольцо */}
                {isActive && (
                  <circle
                    cx={n.x}
                    cy={n.y}
                    r={22}
                    fill="none"
                    stroke={stroke}
                    strokeWidth={1.5}
                    strokeDasharray="3 3"
                  />
                )}

                {n.role === "user" ? (
                  <rect
                    className={styles.nodeBg}
                    x={n.x - 14}
                    y={n.y - 14}
                    width={28}
                    height={28}
                    fill={fill}
                    stroke={stroke}
                    strokeWidth={1.5}
                  />
                ) : n.role === "system" ? (
                  <polygon
                    className={styles.nodeBg}
                    points={`${n.x},${n.y - 16} ${n.x + 16},${n.y} ${n.x},${n.y + 16} ${n.x - 16},${n.y}`}
                    fill={fill}
                    stroke={stroke}
                    strokeWidth={1.5}
                  />
                ) : (
                  <circle
                    className={styles.nodeBg}
                    cx={n.x}
                    cy={n.y}
                    r={14}
                    fill={fill}
                    stroke={stroke}
                    strokeWidth={1.5}
                  />
                )}

                <text
                  x={n.x}
                  y={n.y + 4}
                  textAnchor="middle"
                  fontFamily="var(--mono)"
                  fontSize={10}
                  fontWeight={700}
                  fill={textColor}
                  style={{ pointerEvents: "none" }}
                >
                  {n.role === "user" ? "U" : n.role === "system" ? "S" : "A"}
                </text>

                {/* Подпись ветки рядом с узлом */}
                {n.branchLabel && (
                  <text
                    x={n.x + 22}
                    y={n.y + 4}
                    fontFamily="var(--mono)"
                    fontSize={9}
                    fill={n.branchColor}
                    style={{ pointerEvents: "none" }}
                  >
                    {n.branchLabel}
                  </text>
                )}

                {/* Индикатор стрима */}
                {n.status === "streaming" && (
                  <circle
                    cx={n.x + 14}
                    cy={n.y - 14}
                    r={3}
                    fill="var(--yellow)"
                  >
                    <animate
                      attributeName="opacity"
                      from="0.3"
                      to="1"
                      dur="0.8s"
                      repeatCount="indefinite"
                    />
                  </circle>
                )}
                {n.status === "failed" && (
                  <text
                    x={n.x + 18}
                    y={n.y - 12}
                    fontFamily="var(--mono)"
                    fontSize={10}
                    fill="var(--red)"
                    fontWeight={700}
                    style={{ pointerEvents: "none" }}
                  >
                    !
                  </text>
                )}
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
