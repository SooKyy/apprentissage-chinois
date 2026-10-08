import { useEffect, useState } from "react";
import { api, errorMessage } from "../api";
import type { Settings, Status, WordBrief, WordFull } from "../types";
import { Button, Notice, Tian, Title, Zh, statusLabel } from "../ui";
import { WordAnswer } from "./WordView";

function WordRow({ word, onOpen }: { word: WordBrief; onOpen: (id: number) => void }) {
  return (
    <li>
      <button
        type="button"
        onClick={() => onOpen(word.id)}
        className="flex w-full items-baseline gap-3 border-b border-line py-3 text-left"
      >
        <Zh className="shrink-0 text-2xl">{word.simp}</Zh>
        <span className="min-w-0 flex-1">
          <span className="block text-sm text-soft">{word.pinyin}</span>
          <span className="block truncate">{word.gloss_fr || word.gloss_en}</span>
        </span>
        {word.status && <span className="shrink-0 text-xs text-action">{statusLabel[word.status]}</span>}
      </button>
    </li>
  );
}

function WordPage({ id, settings, onBack }: { id: number; settings: Settings; onBack: () => void }) {
  const [word, setWord] = useState<WordFull | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api<WordFull>(`/api/words/${id}`)
      .then(setWord)
      .catch((cause) => setError(errorMessage(cause)));
  }, [id]);

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await action();
      setWord(await api<WordFull>(`/api/words/${id}`));
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  const setStatus = (status: Status) => run(() => api(`/api/words/${id}/status`, "PUT", { status, source: "dico" }));

  return (
    <div className="flex flex-col gap-5">
      <button type="button" onClick={onBack} className="self-start text-action underline">
        Retour aux résultats
      </button>
      {error && <Notice tone="seal">{error}</Notice>}
      {!word ? (
        !error && <Notice>Chargement…</Notice>
      ) : (
        <>
          <Tian text={word.simp} />
          <WordAnswer word={word} rate={settings.tts_rate} showEnglish={settings.show_english} />
          <p className="text-sm text-soft">
            {[
              word.freq_rank && `${word.freq_rank}ᵉ mot le plus fréquent`,
              word.hsk && (word.hsk === 7 ? "HSK 7 à 9" : `HSK ${word.hsk}`),
              word.status && statusLabel[word.status].toLowerCase(),
            ]
              .filter(Boolean)
              .join(", ")}
          </p>
          <div className="flex flex-col gap-2">
            {word.status !== "learning" && (
              <Button tone="action" disabled={busy} onClick={() => void setStatus("learning")}>
                Apprendre ce mot
              </Button>
            )}
            {word.status !== "known" && (
              <Button disabled={busy} onClick={() => void setStatus("known")}>
                Je le connais déjà
              </Button>
            )}
            {!word.enriched && (
              <Button disabled={busy} onClick={() => void run(() => api(`/api/words/${id}/enrich`, "POST"))}>
                {busy ? "Un instant…" : "Ajouter des phrases d'exemple"}
              </Button>
            )}
            {word.status && (
              <button
                type="button"
                disabled={busy}
                onClick={() => void run(() => api(`/api/words/${id}/status`, "DELETE"))}
                className="min-h-10 text-sm text-soft underline"
              >
                Retirer de mes mots
              </button>
            )}
          </div>
        </>
      )}
    </div>
  );
}

export function Search({ active, settings }: { active: boolean; settings: Settings }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<WordBrief[] | null>(null);
  const [mine, setMine] = useState<{ total: number; words: WordBrief[] } | null>(null);
  const [list, setList] = useState<Status>("learning");
  const [openId, setOpenId] = useState<number | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const text = query.trim();
    if (!text) {
      setResults(null);
      return;
    }
    const timer = setTimeout(() => {
      api<WordBrief[]>(`/api/words/search?q=${encodeURIComponent(text)}`)
        .then((found) => {
          setResults(found);
          setError("");
        })
        .catch((cause) => setError(errorMessage(cause)));
    }, 250);
    return () => clearTimeout(timer);
  }, [query, openId]);

  useEffect(() => {
    if (!active || query.trim() || openId !== null) return;
    api<{ total: number; words: WordBrief[] }>(`/api/words/mine?status=${list}&limit=200`)
      .then(setMine)
      .catch((cause) => setError(errorMessage(cause)));
  }, [active, list, query, openId]);

  if (openId !== null) return <WordPage id={openId} settings={settings} onBack={() => setOpenId(null)} />;

  return (
    <>
      <Title>Chercher</Title>
      <label className="mb-4 flex flex-col gap-1 text-sm text-soft">
        Un mot en chinois, en pinyin ou en français
        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          autoCapitalize="off"
          autoComplete="off"
          className="min-h-12 rounded-md border border-line bg-sheet px-3 text-lg text-ink"
        />
      </label>
      {error && <Notice tone="seal">{error}</Notice>}
      {query.trim() ? (
        results &&
        (results.length ? (
          <ul>
            {results.map((word) => (
              <WordRow key={word.id} word={word} onOpen={setOpenId} />
            ))}
          </ul>
        ) : (
          <p>Aucun mot trouvé pour « {query.trim()} ».</p>
        ))
      ) : (
        <>
          <div className="mb-2 flex gap-2" role="group" aria-label="Mes mots">
            {(["learning", "known", "ignored"] as const).map((status) => (
              <button
                key={status}
                type="button"
                aria-pressed={list === status}
                onClick={() => setList(status)}
                className={`min-h-10 rounded-md border px-3 text-sm ${
                  list === status ? "border-action bg-action text-on-action" : "border-line bg-sheet"
                }`}
              >
                {statusLabel[status]}
              </button>
            ))}
          </div>
          {mine &&
            (mine.words.length ? (
              <>
                <p className="text-sm text-soft">
                  {mine.total} mots{mine.total > mine.words.length && `, les ${mine.words.length} derniers affichés`}
                </p>
                <ul>
                  {mine.words.map((word) => (
                    <WordRow key={word.id} word={{ ...word, status: null }} onOpen={setOpenId} />
                  ))}
                </ul>
              </>
            ) : (
              <p className="mt-3 text-soft">Aucun mot dans cette liste.</p>
            ))}
        </>
      )}
    </>
  );
}
