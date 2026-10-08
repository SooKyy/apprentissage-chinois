import { type FormEvent, useState } from "react";
import { api, errorMessage } from "../api";
import type { Correction, Explanation } from "../types";
import { Button, HAN, Notice, Play, Title, Zh } from "../ui";

function Copyable({ text, pinyin }: { text: string; pinyin: string }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  }
  return (
    <div className="flex items-start gap-3">
      <Play text={text} />
      <div className="min-w-0 flex-1">
        <Zh className="block text-2xl leading-snug">{text}</Zh>
        <div className="text-sm text-soft">{pinyin}</div>
      </div>
      <button type="button" onClick={copy} className="min-h-10 shrink-0 text-sm text-action underline">
        {copied ? "Copié" : "Copier"}
      </button>
    </div>
  );
}

function Explain() {
  const [text, setText] = useState("");
  const [result, setResult] = useState<Explanation | null>(null);
  const [learning, setLearning] = useState<Set<number>>(new Set());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      setResult(await api<Explanation>("/api/assist/explain", "POST", { text: text.trim() }));
      setLearning(new Set());
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  async function learn(wordId: number) {
    try {
      await api(`/api/words/${wordId}/status`, "PUT", { status: "learning", source: "llm" });
      setLearning((current) => new Set(current).add(wordId));
    } catch (cause) {
      setError(errorMessage(cause));
    }
  }

  return (
    <>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <label className="flex flex-col gap-1 text-sm text-soft">
          Une phrase en chinois que tu veux comprendre
          <textarea
            lang="zh-Hans"
            rows={3}
            maxLength={600}
            value={text}
            onChange={(event) => setText(event.target.value)}
            className="rounded-md border border-line bg-sheet p-3 text-xl text-ink"
          />
        </label>
        <Button type="submit" tone="action" disabled={busy || !HAN.test(text)}>
          {busy ? "Un instant…" : "Expliquer"}
        </Button>
      </form>
      {error && <Notice tone="seal">{error}</Notice>}
      {result && (
        <div className="reveal mt-6 flex flex-col gap-5">
          <div className="flex items-start gap-3">
            <Play text={result.texte} />
            <div>
              <Zh className="block text-2xl leading-snug">{result.texte}</Zh>
              <div className="text-sm text-soft">{result.pinyin}</div>
            </div>
          </div>
          <div>
            <p className="text-xl">{result.traduction}</p>
            {result.litteral && <p className="text-sm text-soft">Mot à mot : {result.litteral}</p>}
            {result.registre && <p className="text-sm text-soft">{result.registre}</p>}
          </div>
          <ul>
            {result.mots.map((mot, index) => {
              const known = mot.status !== null || (mot.word_id !== null && learning.has(mot.word_id));
              return (
                <li key={index} className="flex items-baseline gap-3 border-b border-line py-2">
                  <Zh className="shrink-0 text-2xl">{mot.zh}</Zh>
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm text-soft">{mot.pinyin}</span>
                    <span className="block">{mot.sens}</span>
                  </span>
                  {mot.word_id !== null &&
                    (known ? (
                      <span className="shrink-0 text-xs text-soft">Dans mes mots</span>
                    ) : (
                      <button
                        type="button"
                        onClick={() => void learn(mot.word_id!)}
                        className="min-h-10 shrink-0 text-sm text-action underline"
                      >
                        Apprendre
                      </button>
                    ))}
                </li>
              );
            })}
          </ul>
          {result.grammaire.length > 0 && (
            <dl className="flex flex-col gap-3">
              {result.grammaire.map((point, index) => (
                <div key={index}>
                  <dt lang="zh-Hans" className="text-xl">
                    {point.point}
                  </dt>
                  <dd>{point.explication}</dd>
                </div>
              ))}
            </dl>
          )}
        </div>
      )}
    </>
  );
}

function Correct() {
  const [text, setText] = useState("");
  const [intention, setIntention] = useState("");
  const [result, setResult] = useState<Correction | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      setResult(await api<Correction>("/api/assist/correct", "POST", { text: text.trim(), intention: intention.trim() }));
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <label className="flex flex-col gap-1 text-sm text-soft">
          Ton message en chinois
          <textarea
            lang="zh-Hans"
            rows={3}
            maxLength={600}
            value={text}
            onChange={(event) => setText(event.target.value)}
            className="rounded-md border border-line bg-sheet p-3 text-xl text-ink"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm text-soft">
          Ce que tu veux dire, en français (facultatif)
          <input
            value={intention}
            maxLength={300}
            onChange={(event) => setIntention(event.target.value)}
            className="min-h-12 rounded-md border border-line bg-sheet px-3 text-base text-ink"
          />
        </label>
        <Button type="submit" tone="action" disabled={busy || !HAN.test(text)}>
          {busy ? "Un instant…" : "Corriger"}
        </Button>
      </form>
      {error && <Notice tone="seal">{error}</Notice>}
      {result && (
        <div className="reveal mt-6 flex flex-col gap-5">
          <p className={result.correct ? "text-action" : "text-seal"}>
            {result.correct ? "Ton message est correct." : "Quelques points à corriger."}
          </p>
          <div>
            <h2 className="mb-2 font-bold">{result.correct ? "Ton message" : "Version corrigée"}</h2>
            <Copyable text={result.corrige} pinyin={result.corrige_pinyin} />
            {result.traduction && <p className="mt-2 text-soft">{result.traduction}</p>}
          </div>
          {result.naturel !== result.corrige && (
            <div>
              <h2 className="mb-2 font-bold">Comme le dirait un natif</h2>
              <Copyable text={result.naturel} pinyin={result.naturel_pinyin} />
            </div>
          )}
          {result.erreurs.length > 0 && (
            <ul className="flex flex-col gap-3">
              {result.erreurs.map((item, index) => (
                <li key={index} className="border-l-2 border-seal pl-3">
                  <p lang="zh-Hans" className="text-xl">
                    <s className="text-seal">{item.original}</s> {item.correction}
                  </p>
                  <p>{item.explication}</p>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </>
  );
}

export function Assist() {
  const [mode, setMode] = useState<"explain" | "correct">("explain");
  return (
    <>
      <Title>Demander</Title>
      <div className="mb-5 flex gap-2" role="group" aria-label="Type de demande">
        {(
          [
            ["explain", "Comprendre"],
            ["correct", "Corriger"],
          ] as const
        ).map(([value, label]) => (
          <button
            key={value}
            type="button"
            aria-pressed={mode === value}
            onClick={() => setMode(value)}
            className={`min-h-10 flex-1 rounded-md border px-3 text-sm ${
              mode === value ? "border-action bg-action text-on-action" : "border-line bg-sheet"
            }`}
          >
            {label}
          </button>
        ))}
      </div>
      <div hidden={mode !== "explain"}>
        <Explain />
      </div>
      <div hidden={mode !== "correct"}>
        <Correct />
      </div>
      <p className="mt-6 text-sm text-soft">
        Ce que tu écris ici est envoyé au modèle DeepSeek via OpenRouter. Rien n'est envoyé sans que tu appuies sur le bouton.
      </p>
    </>
  );
}
