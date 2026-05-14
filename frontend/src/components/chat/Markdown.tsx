"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import "highlight.js/styles/github-dark.css";
import styles from "./Markdown.module.css";

interface Props {
  content: string;
}

/**
 * Рендер markdown-ответа от LLM.
 *
 * Используется:
 *   • remark-gfm — таблицы, чек-листы, strikethrough, autolinks;
 *   • rehype-highlight — подсветка кода (тема github-dark импортирована
 *     глобально из CSS-файла highlight.js).
 *
 * Все ссылки открываются в новой вкладке.
 */
export function Markdown({ content }: Props) {
  return (
    <div className={styles.md}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={{
          a: ({ node, ...props }) => (
            <a {...props} target="_blank" rel="noopener noreferrer" />
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
