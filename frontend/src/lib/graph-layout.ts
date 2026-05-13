import type { MessageDTO } from "@/lib/chat-types";

export interface GraphNode {
  id: string;
  role: "user" | "assistant" | "system";
  status: MessageDTO["status"];
  parent_id: string | null;
  depth: number;        // y-уровень в дереве
  branchIndex: number;  // x-позиция в этой полосе
  isCurrent: boolean;
  branchLabel: string | null;
  // Координаты на холсте
  x: number;
  y: number;
  // Для группировки UI: «индекс ветки» из всех листьев
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

const BRANCH_COLORS = [
  "#1E7A3C", // green — main
  "#E8B71A", // yellow — alt-a
  "#C8202B", // red   — alt-b
  "#8A8170", // muted — далее
];

const NODE_GAP_X = 110;
const NODE_GAP_Y = 90;
const NODE_PADDING = 60;

/**
 * Раскладывает дерево сообщений в координаты для SVG.
 * Алгоритм: BFS от корня; для каждого узла высота = глубина (parent.depth+1),
 * x-позиция = текущая колонка в полосе уровня. Простой walk-based layout.
 */
export function layoutGraph(
  messages: MessageDTO[],
  currentMessageId: string | null,
): GraphLayout {
  if (messages.length === 0) {
    return { nodes: [], edges: [], width: 0, height: 0 };
  }

  // Индекс по id и список детей по parent_id
  const byId = new Map<string, MessageDTO>();
  const children = new Map<string | null, string[]>();
  for (const m of messages) {
    byId.set(m.id, m);
    const arr = children.get(m.parent_id) ?? [];
    arr.push(m.id);
    children.set(m.parent_id, arr);
  }

  // Сортируем детей по created_at — это нам гарантирует API
  // (find_for_chat order by created_at asc)

  // Назначим каждому листу свой branchIndex; внутренним узлам — branchIndex
  // первого ребёнка (чтобы main-ветка шла по центру).
  const branchIndexOf = new Map<string, number>();
  const depthOf = new Map<string, number>();

  // Найдём корни (parent_id === null)
  const roots = children.get(null) ?? [];

  // DFS, выдавая branchIndex по порядку обхода
  let nextBranch = 0;

  function dfs(id: string, depth: number): number {
    depthOf.set(id, depth);
    const kids = children.get(id) ?? [];
    if (kids.length === 0) {
      const b = nextBranch++;
      branchIndexOf.set(id, b);
      return b;
    }
    let firstBranch = -1;
    for (const kid of kids) {
      const b = dfs(kid, depth + 1);
      if (firstBranch < 0) firstBranch = b;
    }
    branchIndexOf.set(id, firstBranch);
    return firstBranch;
  }

  for (const root of roots) dfs(root, 0);

  // Когда у узла несколько детей — нужно их визуально разнести.
  // Делаем простую "колонку на ветку": branchIndex напрямую = X-колонка.
  const nodes: GraphNode[] = messages.map((m) => {
    const depth = depthOf.get(m.id) ?? 0;
    const branchIndex = branchIndexOf.get(m.id) ?? 0;
    const color = BRANCH_COLORS[branchIndex] ?? BRANCH_COLORS[BRANCH_COLORS.length - 1];
    return {
      id: m.id,
      role: m.role,
      status: m.status,
      parent_id: m.parent_id,
      depth,
      branchIndex,
      isCurrent: m.id === currentMessageId,
      branchLabel: m.branch_label,
      branchColor: color,
      x: NODE_PADDING + branchIndex * NODE_GAP_X,
      y: NODE_PADDING + depth * NODE_GAP_Y,
    };
  });

  const edges: GraphEdge[] = [];
  for (const m of messages) {
    if (m.parent_id) edges.push({ fromId: m.parent_id, toId: m.id });
  }

  const maxBranch = Math.max(0, ...nodes.map((n) => n.branchIndex));
  const maxDepth = Math.max(0, ...nodes.map((n) => n.depth));

  return {
    nodes,
    edges,
    width: NODE_PADDING * 2 + maxBranch * NODE_GAP_X + 40,
    height: NODE_PADDING * 2 + maxDepth * NODE_GAP_Y + 40,
  };
}
