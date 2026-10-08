import { type ButtonHTMLAttributes, type CSSProperties, type ReactNode, useState } from "react";
import { speak } from "./audio";

export const HAN = /[㐀-䶿一-鿿]/;

export function Zh({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <span lang="zh-Hans" className={className}>
      {children}
    </span>
  );
}

/** Le mot posé dans des cases de cahier, un caractère par case. */
export function Tian({ text, small = false }: { text: string; small?: boolean }) {
  const chars = Array.from(text);
  return (
    <div
      lang="zh-Hans"
      className={`tian ${small ? "small" : ""}`}
      style={{ "--count": chars.length } as CSSProperties}
      aria-label={text}
    >
      {chars.map((char, index) => (
        <span key={index} aria-hidden="true">
          {char}
        </span>
      ))}
    </div>
  );
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { tone?: "action" | "plain" | "seal" };

export function Button({ tone = "plain", className = "", ...props }: ButtonProps) {
  const tones = {
    action: "bg-action text-on-action border-action font-bold",
    plain: "bg-sheet text-ink border-line",
    seal: "bg-sheet text-seal border-seal",
  };
  return (
    <button
      type="button"
      {...props}
      className={`min-h-12 rounded-md border px-4 py-2 text-base active:translate-y-px ${tones[tone]} ${className}`}
    />
  );
}

export function Play({ text, rate = 1, label = "Écouter", big = false }: { text: string; rate?: number; label?: string; big?: boolean }) {
  const [failed, setFailed] = useState(false);
  const size = big ? "h-24 w-24 text-4xl" : "h-10 w-10 text-lg";
  return (
    <button
      type="button"
      aria-label={`${label} : ${text}`}
      title={failed ? "Audio indisponible" : label}
      onClick={async () => setFailed(!(await speak(text, rate)))}
      className={`inline-grid shrink-0 place-items-center rounded-full border ${size} ${
        failed ? "border-seal text-seal" : "border-grid text-action"
      } bg-sheet`}
    >
      <svg viewBox="0 0 24 24" className={big ? "h-10 w-10" : "h-5 w-5"} fill="currentColor" aria-hidden="true">
        <path d="M4 9v6h4l5 4V5L8 9H4zm11.5 3a3.5 3.5 0 0 0-2-3.15v6.3a3.5 3.5 0 0 0 2-3.15zM13.5 4.3v2.1a6 6 0 0 1 0 11.2v2.1a8 8 0 0 0 0-15.4z" />
      </svg>
    </button>
  );
}

export function Notice({ children, tone = "soft" }: { children: ReactNode; tone?: "soft" | "seal" }) {
  return (
    <p role={tone === "seal" ? "alert" : undefined} className={`text-sm ${tone === "seal" ? "text-seal" : "text-soft"}`}>
      {children}
    </p>
  );
}

export function Meter({ parts, total, label }: { parts: { value: number; className: string }[]; total: number; label: string }) {
  return (
    <div className="flex h-2 overflow-hidden rounded-full bg-line" role="img" aria-label={label}>
      {parts.map((part, index) => (
        <div key={index} className={part.className} style={{ width: `${total ? (100 * part.value) / total : 0}%` }} />
      ))}
    </div>
  );
}

export function Title({ children, aside }: { children: ReactNode; aside?: ReactNode }) {
  return (
    <header className="mb-5 flex items-baseline justify-between gap-3">
      <h1 className="text-2xl font-bold">{children}</h1>
      {aside}
    </header>
  );
}

export const statusLabel = { learning: "En cours", known: "Connu", ignored: "Ignoré" } as const;
