import React from "react";

/** Tiny, dependency-free markdown renderer for the demo answers.
 *  Line-based so a heading and the body line right after it render as
 *  separate elements (### title, then its paragraph). Supports bold,
 *  ###, blockquote, and bullet lists. */
export function Markdown({ text }: { text: string }) {
  const lines = text.trim().split("\n");
  const out: React.ReactNode[] = [];
  let list: string[] = [];
  let key = 0;

  const flush = () => {
    if (list.length) {
      const items = [...list];
      out.push(
        <ul key={key++} className="space-y-1.5 pl-1">
          {items.map((l, i) => (
            <li key={i} className="flex gap-2 text-[var(--text-2)]">
              <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full brand-gradient" />
              <span>{inline(l)}</span>
            </li>
          ))}
        </ul>,
      );
      list = [];
    }
  };

  for (const raw of lines) {
    const line = raw.trim();
    if (!line) { flush(); continue; }
    if (line.startsWith("- ")) { list.push(line.slice(2)); continue; }
    flush();
    if (line.startsWith("### ")) {
      out.push(<h3 key={key++} className="mt-1 text-[15px] font-semibold text-[var(--text)]">{inline(line.slice(4))}</h3>);
    } else if (line.startsWith("> ")) {
      out.push(
        <blockquote key={key++} className="rounded-r-lg border-l-2 border-[var(--accent-violet)] bg-white/[0.03] py-2 pl-3 text-[var(--text-2)]">
          {inline(line.slice(2))}
        </blockquote>,
      );
    } else {
      out.push(<p key={key++} className="text-[var(--text-2)]">{inline(line)}</p>);
    }
  }
  flush();

  return <div className="space-y-2.5 text-[14.5px] leading-relaxed">{out}</div>;
}

function inline(s: string): React.ReactNode {
  return s.split(/(\*\*[^*]+\*\*)/g).map((p, i) =>
    p.startsWith("**") && p.endsWith("**") ? (
      <strong key={i} className="font-semibold text-[var(--text)]">
        {p.slice(2, -2)}
      </strong>
    ) : (
      <React.Fragment key={i}>{p}</React.Fragment>
    ),
  );
}
