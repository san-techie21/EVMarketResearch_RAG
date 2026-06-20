import React from "react";

/** Tiny, dependency-free markdown renderer for the demo answers
 *  (bold, ###, blockquote, bullet lists, paragraphs). */
export function Markdown({ text }: { text: string }) {
  const blocks = text.trim().split(/\n\n+/);
  return (
    <div className="space-y-3 text-[14.5px] leading-relaxed">
      {blocks.map((b, i) => (
        <Block key={i} b={b} />
      ))}
    </div>
  );
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

function Block({ b }: { b: string }) {
  if (b.startsWith("### "))
    return <h3 className="mt-1 text-[15px] font-semibold text-[var(--text)]">{inline(b.slice(4))}</h3>;
  if (b.startsWith("> "))
    return (
      <blockquote className="rounded-r-lg border-l-2 border-[var(--accent-violet)] bg-white/[0.03] py-2 pl-3 text-[var(--text-2)]">
        {inline(b.slice(2))}
      </blockquote>
    );
  if (/^- /m.test(b)) {
    const items = b.split(/\n/).filter((l) => l.trim().startsWith("- "));
    return (
      <ul className="space-y-1.5 pl-1">
        {items.map((l, i) => (
          <li key={i} className="flex gap-2 text-[var(--text-2)]">
            <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full brand-gradient" />
            <span>{inline(l.replace(/^- /, ""))}</span>
          </li>
        ))}
      </ul>
    );
  }
  return <p className="text-[var(--text-2)]">{inline(b)}</p>;
}
