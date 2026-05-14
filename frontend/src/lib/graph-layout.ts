import type { MessageDTO } from "@/lib/chat-types";

export interface GraphNode {
  id: string;
  role: "user" | "assistant" | "system";
  status: MessageDTO["status"];
  parent_id: string | null;
  depth: number;        // x-уровень: сколько шагов от корня
  branchIndex: number;  // 0 = main; 1, 2, ... = альтернативные ветки
  isCurrent: boolean;
  branchLabel: string | null;
  x: number;            // pixel x
  y: number;            // pixel y
  branchColor: string;
}

export interface GraphEdge {
  fromId: string;
  toId: string;
}

export interface GraphLayout {
  nodes: GraphNode[];
  edges: GraphEdge[];
  width: number;
  height: number;
}

// Цветовая палитра веток: main = текст (нейтральный), alt-* = бренд-цвета.
// Красный мы НЕ используем для веток — он зарезервирован под ошибки/role.
const BRANCH_COLORS = [
  "var(--text)",     // main
  "var(--yellow)",   // alt-a
  "var(--green)",    // alt-b
  "var(--muted)",    // дальше
];

const STEP_X = 150;
const LANE_Y = 95;
const PAD_X = 60;
const PAD_Y = 70;

/**
 * Раскладывает дерево сообщений в координаты для SVG.
 *
 * Идеи:
 *   • х растёт с глубиной (диалог разворачивается слева направо);
 *   • main-ветка (первый ребёнок каждого parent) идёт по центральной полосе;
 *   • альтернативные ветки разводятся вверх/вниз по «полосам».
 *
 * Алгоритм:
 *   1) DFS считает depth каждого узла (расстояние от корня).
 *   2) Каждому узлу присваиваем lane: у первого ребёнка = lane родителя,
 *      у последующих детей — поочерёдно ±1, ±2 относительно lane родителя.
 *   3) Конвертируем (depth, lane) → (x, y).
 */
export function layoutGraph(
  messages: MessageDTO[],
  currentMessageId: string | null,
): GraphLayout {
  if (messages.length === 0) {
    return { nodes: [], edges: [], width: 0, height: 0 };
  }

  // Сообщения у нас уже упорядочены по created_at (бэкенд так возвращает),
  // дети будут добавляться в порядке появления — это важно для разводки веток.
  const byId = new Map(messages.map((m) => [m.id, m]));
  const children = new Map<string | null, string[]>();
  for (const m of messages) {
    const arr = children.get(m.parent_id) ?? [];
    arr.push(m.id);
    children.set(m.parent_id, arr);
  }

  const depthOf = new Map<string, number>();
  const laneOf = new Map<string, number>();
  const branchOf = new Map<string, number>();

  function walk(id: string, depth: number, lane: number, branch: number) {
    depthOf.set(id, depth);
    laneOf.set(id, lane);
    branchOf.set(id, branch);

    const kids = children.get(id) ?? [];
    // Первый ребёнок — продолжает текущую ветку
    kids.forEach((kid, i) => {
      if (i === 0) {
        walk(kid, depth + 1, lane, branch);
      } else {
        // Альтернативные дети — разводятся ±1, ±2 от lane родителя
        const offset = altOffset(i);
        walk(kid, depth + 1, lane + offset, branch + i);
      }
    });
  }

  // Корни (parent_id === null), главный — по центру (lane=0)
  const roots = children.get(null) ?? [];
  roots.forEach((rootId, i) => {
    walk(rootId, 0, i === 0 ? 0 : altOffset(i), i);
  });

  // Найдём диапазон lanes чтобы сдвинуть к нулю
  const lanes = [...laneOf.values()];
  const minLane = Math.min(0, ...lanes);
  const depths = [...depthOf.values()];
  const maxDepth = Math.max(0, ...depths);

  const nodes: GraphNode[] = messages.map((m) => {
    const depth = depthOf.get(m.id) ?? 0;
    const lane = laneOf.get(m.id) ?? 0;
    const branch = branchOf.get(m.id) ?? 0;
    const color = BRANCH_COLORS[Math.min(branch, BRANCH_COLORS.length - 1)];
    return {
      id: m.id,
      role: m.role,
      status: m.status,
      parent_id: m.parent_id,
      depth,
      branchIndex: branch,
      isCurrent: m.id === currentMessageId,
      branchLabel: m.branch_label,
      branchColor: color,
      x: PAD_X + depth * STEP_X,
      y: PAD_Y + (lane - minLane) * LANE_Y,
    };
  });

  const edges: GraphEdge[] = [];
  for (const m of messages) {
    if (m.parent_id) edges.push({ fromId: m.parent_id, toId: m.id });
  }

  const width = PAD_X * 2 + maxDepth * STEP_X + 40;
  const height = PAD_Y * 2 + (Math.max(...lanes) - minLane + 1) * LANE_Y;

  return { nodes, edges, width, height };
}

/**
 * Смещение полосы для i-го альтернативного ребёнка:
 * 1 → +1, 2 → -1, 3 → +2, 4 → -2, ...
 */
function altOffset(i: number): number {
  const sign = i % 2 === 1 ? 1 : -1;
  const magnitude = Math.ceil(i / 2);
  return sign * magnitude;
}
