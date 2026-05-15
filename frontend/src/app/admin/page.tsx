"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ChatSidebar } from "@/components/chat/ChatSidebar";
import { api, ApiHttpError } from "@/lib/api";
import { useAuthStore } from "@/lib/auth-store";
import type { UserDTO } from "@/lib/api-types";
import { KHASA } from "@/styles/tokens";
import styles from "./admin.module.css";

type Tab = "pending" | "all" | "sandboxes";

interface SandboxRow {
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
}

export default function AdminPage() {
  const router = useRouter();
  const { user, initialized, bootstrap } = useAuthStore();

  const [tab, setTab] = useState<Tab>("pending");
  const [pending, setPending] = useState<UserDTO[] | null>(null);
  const [all, setAll] = useState<UserDTO[] | null>(null);
  const [sandboxes, setSandboxes] = useState<SandboxRow[] | null>(null);
  const [notice, setNotice] = useState<{ kind: "ok" | "err"; text: string } | null>(null);
  const [acting, setActing] = useState<string | null>(null);
  const [execTarget, setExecTarget] = useState<SandboxRow | null>(null);
  const [execCommand, setExecCommand] = useState("");
  const [execOutput, setExecOutput] = useState<{ exit: number; stdout: string; stderr: string } | null>(null);
  const [execRunning, setExecRunning] = useState(false);

  useEffect(() => {
    bootstrap();
  }, [bootstrap]);

  useEffect(() => {
    if (!initialized) return;
    if (!user) {
      router.replace("/auth/login");
      return;
    }
    if (!user.is_superuser) {
      router.replace("/chat");
    }
  }, [initialized, user, router]);

  const loadPending = useCallback(async () => {
    try {
      const r = await api.users.pending();
      setPending(r.users);
    } catch (err) {
      if (err instanceof ApiHttpError) {
        setNotice({ kind: "err", text: `${err.status}: ${err.detail}` });
      } else {
        setNotice({ kind: "err", text: String(err) });
      }
    }
  }, []);

  const loadAll = useCallback(async () => {
    try {
      const r = await api.users.all();
      setAll(r.users);
    } catch (err) {
      if (err instanceof ApiHttpError) {
        setNotice({ kind: "err", text: `${err.status}: ${err.detail}` });
      } else {
        setNotice({ kind: "err", text: String(err) });
      }
    }
  }, []);

  const loadSandboxes = useCallback(async () => {
    try {
      const r = await api.sandbox.adminList();
      setSandboxes(r.sandboxes);
    } catch (err) {
      if (err instanceof ApiHttpError) {
        setNotice({ kind: "err", text: `${err.status}: ${err.detail}` });
      } else {
        setNotice({ kind: "err", text: String(err) });
      }
    }
  }, []);

  useEffect(() => {
    if (user?.is_superuser) {
      loadPending();
      loadAll();
      loadSandboxes();
    }
  }, [user, loadPending, loadAll, loadSandboxes]);

  const activate = async (id: string, email: string) => {
    setActing(id);
    try {
      await api.users.activate(id);
      setNotice({ kind: "ok", text: `${email} активирован, письмо отправлено` });
      await Promise.all([loadPending(), loadAll()]);
    } catch (err) {
      if (err instanceof ApiHttpError) {
        setNotice({ kind: "err", text: `${err.status}: ${err.detail}` });
      } else {
        setNotice({ kind: "err", text: String(err) });
      }
    } finally {
      setActing(null);
    }
  };

  const deactivate = async (id: string, email: string) => {
    if (!confirm(`Деактивировать ${email}? Юзер не сможет войти.`)) return;
    setActing(id);
    try {
      await api.users.deactivate(id);
      setNotice({ kind: "ok", text: `${email} деактивирован` });
      await loadAll();
    } catch (err) {
      if (err instanceof ApiHttpError) {
        setNotice({ kind: "err", text: `${err.status}: ${err.detail}` });
      } else {
        setNotice({ kind: "err", text: String(err) });
      }
    } finally {
      setActing(null);
    }
  };

  // ── sandbox actions ──────────────────────────────────────────────────────

  const runExec = async () => {
    if (!execTarget || !execCommand.trim()) return;
    setExecRunning(true);
    setExecOutput(null);
    try {
      const r = await api.sandbox.adminExec(execTarget.id, execCommand);
      setExecOutput({ exit: r.exit_code, stdout: r.stdout, stderr: r.stderr });
    } catch (err) {
      setExecOutput({
        exit: -1,
        stdout: "",
        stderr: err instanceof Error ? err.message : String(err),
      });
    } finally {
      setExecRunning(false);
    }
  };

  const removeSandbox = async (sb: SandboxRow) => {
    if (!confirm(`Удалить контейнер ${sb.container_name}?`)) return;
    setActing(sb.id);
    try {
      await api.sandbox.adminRemove(sb.id);
      setNotice({ kind: "ok", text: `контейнер ${sb.container_name} удалён` });
      await loadSandboxes();
    } catch (err) {
      if (err instanceof ApiHttpError) {
        setNotice({ kind: "err", text: `${err.status}: ${err.detail}` });
      } else {
        setNotice({ kind: "err", text: String(err) });
      }
    } finally {
      setActing(null);
    }
  };

  if (!initialized || !user || !user.is_superuser) {
    return (
      <div
        style={{
          minHeight: "100vh",
          display: "grid",
          placeItems: "center",
          color: "var(--muted)",
          fontFamily: "var(--mono)",
          fontSize: 12,
        }}
      >
        [runtime] проверка прав...
      </div>
    );
  }

  const rows: UserDTO[] = (tab === "pending" ? pending : all) ?? [];

  return (
    <div className={styles.layout}>
      <ChatSidebar />

      <div className={styles.root}>
        <div className={styles.topbar}>
          <span className={styles.crumbs}>~/admin/</span>
          <span className={styles.title}>users</span>
          <span style={{ flex: 1 }} />
          <span style={{ fontFamily: "var(--mono)", fontSize: 11, color: "var(--muted)" }}>
            {user.email}
            <span style={{ color: KHASA.yellow, marginLeft: 8 }}>· admin</span>
          </span>
        </div>

      <div className={styles.tabs}>
        <button
          className={`${styles.tab} ${tab === "pending" ? styles.active : ""}`}
          onClick={() => setTab("pending")}
        >
          <span>заявки</span>
          {pending && <span className={styles.badge}>{pending.length}</span>}
        </button>
        <button
          className={`${styles.tab} ${tab === "all" ? styles.active : ""}`}
          onClick={() => setTab("all")}
        >
          <span>все пользователи</span>
          {all && <span className={styles.badge}>{all.length}</span>}
        </button>
        <button
          className={`${styles.tab} ${tab === "sandboxes" ? styles.active : ""}`}
          onClick={() => setTab("sandboxes")}
        >
          <span>контейнеры</span>
          {sandboxes && <span className={styles.badge}>{sandboxes.length}</span>}
        </button>
      </div>

      <div className={styles.content}>
        {notice && (
          <div className={`${styles.notice} ${notice.kind === "err" ? styles.error : ""}`}>
            <span
              style={{
                color: notice.kind === "ok" ? "var(--green)" : "var(--red)",
                fontFamily: "var(--mono)",
                fontWeight: 700,
              }}
            >
              [{notice.kind === "ok" ? "ok" : "err"}]
            </span>
            <span>{notice.text}</span>
            <span style={{ flex: 1 }} />
            <button
              className={styles.smallBtn}
              onClick={() => setNotice(null)}
            >
              ×
            </button>
          </div>
        )}

        <div className={styles.headerRow}>
          <h2>
            {tab === "pending"
              ? "// заявки на одобрение"
              : tab === "all"
                ? "// все пользователи"
                : "// контейнеры-песочницы"}
          </h2>
          <span className={styles.meta}>
            {tab === "pending"
              ? pending?.length ?? 0
              : tab === "all"
                ? all?.length ?? 0
                : sandboxes?.length ?? 0}{" "}
            записей
          </span>
        </div>

        {tab !== "sandboxes" && (rows.length === 0 ? (
          <div className={styles.empty}>
            {tab === "pending"
              ? "// очередь пуста — все заявки рассмотрены"
              : "// пользователей пока нет"}
          </div>
        ) : (
          <table className={styles.table}>
            <thead>
              <tr>
                <th>email</th>
                <th>email подтв.</th>
                <th>активен</th>
                <th>роль</th>
                <th style={{ textAlign: "right" }}>действия</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((u) => {
                const isMe = u.id === user.id;
                return (
                  <tr key={u.id}>
                    <td style={{ color: "var(--text)" }}>{u.email}</td>
                    <td>
                      {u.is_email_verified ? (
                        <span className={styles.pill}>
                          <span
                            className={styles.dot}
                            style={{ background: KHASA.green }}
                          />
                          подтв.
                        </span>
                      ) : (
                        <span className={styles.pill}>
                          <span
                            className={styles.dot}
                            style={{ background: KHASA.red }}
                          />
                          нет
                        </span>
                      )}
                    </td>
                    <td>
                      {u.is_active ? (
                        <span className={styles.pill}>
                          <span
                            className={styles.dot}
                            style={{ background: KHASA.green }}
                          />
                          активен
                        </span>
                      ) : (
                        <span className={styles.pill}>
                          <span
                            className={styles.dot}
                            style={{ background: KHASA.yellow }}
                          />
                          ожидание
                        </span>
                      )}
                    </td>
                    <td style={{ color: "var(--muted)" }}>
                      {u.is_superuser ? (
                        <span style={{ color: KHASA.yellow }}>superuser</span>
                      ) : (
                        "user"
                      )}
                    </td>
                    <td>
                      <div className={styles.actions}>
                        {tab === "pending" && (
                          <button
                            className={`${styles.smallBtn} ${styles.primary}`}
                            disabled={acting === u.id}
                            onClick={() => activate(u.id, u.email)}
                          >
                            {acting === u.id ? "..." : "активировать"}
                          </button>
                        )}
                        {tab === "all" && u.is_active && !isMe && (
                          <button
                            className={`${styles.smallBtn} ${styles.danger}`}
                            disabled={acting === u.id}
                            onClick={() => deactivate(u.id, u.email)}
                          >
                            деактивировать
                          </button>
                        )}
                        {tab === "all" && !u.is_active && u.is_email_verified && (
                          <button
                            className={`${styles.smallBtn} ${styles.primary}`}
                            disabled={acting === u.id}
                            onClick={() => activate(u.id, u.email)}
                          >
                            активировать
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ))}

        {tab === "sandboxes" && (
          sandboxes === null ? (
            <div className={styles.empty}>// загрузка…</div>
          ) : sandboxes.length === 0 ? (
            <div className={styles.empty}>
              // песочниц не создано (включи агентный режим в чате)
            </div>
          ) : (
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>контейнер</th>
                  <th>chat / user</th>
                  <th>статус БД</th>
                  <th>статус Docker</th>
                  <th>image</th>
                  <th style={{ textAlign: "right" }}>действия</th>
                </tr>
              </thead>
              <tbody>
                {sandboxes.map((sb) => {
                  const live = sb.status_live || "—";
                  const liveColor =
                    live === "running"
                      ? "var(--green)"
                      : live === "exited"
                        ? "var(--red)"
                        : "var(--muted)";
                  return (
                    <tr key={sb.id}>
                      <td style={{ color: "var(--text)" }}>
                        <code style={{ fontSize: 11 }}>{sb.container_name}</code>
                        {sb.error && (
                          <div style={{ color: "var(--red)", fontSize: 10 }}>
                            err: {sb.error}
                          </div>
                        )}
                      </td>
                      <td>
                        <code style={{ fontSize: 10, color: "var(--muted)" }}>
                          {sb.chat_id.slice(0, 8)} / {sb.user_id.slice(0, 8)}
                        </code>
                      </td>
                      <td>
                        <span className={styles.pill}>{sb.status_db}</span>
                      </td>
                      <td>
                        <span
                          className={styles.pill}
                          style={{ color: liveColor, borderColor: liveColor }}
                        >
                          {live}
                        </span>
                      </td>
                      <td>
                        <code style={{ fontSize: 10 }}>{sb.image}</code>
                      </td>
                      <td>
                        <div className={styles.actions}>
                          <button
                            className={styles.smallBtn}
                            onClick={() => {
                              setExecTarget(sb);
                              setExecCommand("");
                              setExecOutput(null);
                            }}
                            disabled={!sb.container_id || live !== "running"}
                          >
                            exec
                          </button>
                          <button
                            className={`${styles.smallBtn} ${styles.danger}`}
                            onClick={() => removeSandbox(sb)}
                            disabled={acting === sb.id}
                          >
                            удалить
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )
        )}

        {execTarget && (
          <div
            className={styles.notice}
            style={{
              marginTop: 16,
              display: "flex",
              flexDirection: "column",
              alignItems: "stretch",
              gap: 8,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <strong style={{ fontFamily: "var(--mono)", fontSize: 11 }}>
                exec → {execTarget.container_name}
              </strong>
              <span style={{ flex: 1 }} />
              <button
                className={styles.smallBtn}
                onClick={() => {
                  setExecTarget(null);
                  setExecOutput(null);
                }}
              >
                закрыть
              </button>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <input
                type="text"
                value={execCommand}
                onChange={(e) => setExecCommand(e.target.value)}
                placeholder='например: ls -la /workspace'
                style={{
                  flex: 1,
                  background: "var(--bg)",
                  border: "1px solid var(--rule)",
                  borderRadius: "var(--r-sm)",
                  color: "var(--text)",
                  fontFamily: "var(--mono)",
                  fontSize: 12,
                  padding: "8px 10px",
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter") runExec();
                }}
              />
              <button
                className={`${styles.smallBtn} ${styles.primary}`}
                onClick={runExec}
                disabled={execRunning || !execCommand.trim()}
              >
                {execRunning ? "…" : "run"}
              </button>
            </div>
            {execOutput && (
              <div
                style={{
                  background: "var(--bg)",
                  border: "1px solid var(--rule)",
                  borderRadius: "var(--r-sm)",
                  padding: "8px 10px",
                  fontFamily: "var(--mono)",
                  fontSize: 11.5,
                  maxHeight: 320,
                  overflow: "auto",
                }}
              >
                <div style={{ color: "var(--muted)" }}>
                  exit {execOutput.exit}
                </div>
                {execOutput.stdout && (
                  <pre style={{ margin: "6px 0", whiteSpace: "pre-wrap" }}>
                    {execOutput.stdout}
                  </pre>
                )}
                {execOutput.stderr && (
                  <pre
                    style={{
                      margin: "6px 0",
                      whiteSpace: "pre-wrap",
                      color: "var(--red)",
                    }}
                  >
                    {execOutput.stderr}
                  </pre>
                )}
              </div>
            )}
          </div>
        )}
      </div>
      </div>
    </div>
  );
}
