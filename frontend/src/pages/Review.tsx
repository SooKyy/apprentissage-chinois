import { type FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { api, errorMessage } from "../api";
import { preload, speak, stop } from "../audio";
import type { Card, Queue, QueueCounts, Settings, WordFull } from "../types";
import { Button, Notice, Play, Tian, Zh } from "../ui";
import { WordAnswer } from "./WordView";

const KIND_LABEL = { reco: "Lecture", ecoute: "Écoute", prod: "Écriture" } as const;
const RATINGS = [
  { value: 1, label: "Oublié", tone: "seal" },
  { value: 2, label: "Difficile", tone: "plain" },
  { value: 3, label: "Bien", tone: "action" },
  { value: 4, label: "Facile", tone: "plain" },
] as const;
const MAX_AUTO_ENRICH = 12;

export function Review({ settings }: { settings: Settings }) {
  const [cards, setCards] = useState<Card[] | null>(null);
  const [counts, setCounts] = useState<QueueCounts | null>(null);
  const [batch, setBatch] = useState(0);
  const [revealed, setRevealed] = useState(false);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [canUndo, setCanUndo] = useState(false);
  const shownAt = useRef(Date.now());
  const rate = settings.tts_rate;

  const load = useCallback(async () => {
    const queue = await api<Queue>("/api/review/queue");
    setCards(queue.cards);
    setCounts(queue.counts);
    setBatch((value) => value + 1);
  }, []);

  useEffect(() => {
    load().catch((cause) => setError(errorMessage(cause)));
    return stop;
  }, [load]);

  const card = cards?.[0];
  const cardKey = card ? `${card.id}:${card.reps}` : "";
  const sentenceIndex = card && card.word.sentences.length ? card.reps % card.word.sentences.length : undefined;
  const sentence = card && sentenceIndex !== undefined ? card.word.sentences[sentenceIndex] : undefined;

  // Nouvelle carte à l'écran : on repart de zéro, et une carte d'écoute se lit toute seule
  useEffect(() => {
    if (!card) return;
    shownAt.current = Date.now();
    setRevealed(false);
    setTyped("");
    if (card.kind === "ecoute") void speak(card.word.simp, rate);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cardKey]);

  useEffect(() => {
    cards?.slice(0, 3).forEach((item) => void preload(item.word.simp).catch(() => undefined));
  }, [cards]);

  // Sens français court et phrases d'exemple pour les mots qui n'en ont pas encore, en arrière-plan
  useEffect(() => {
    if (!settings.auto_enrich || !cards) return;
    let cancelled = false;
    const pending = [...new Set(cards.filter((item) => !item.word.enriched).map((item) => item.word.id))];
    (async () => {
      for (const wordId of pending.slice(0, MAX_AUTO_ENRICH)) {
        if (cancelled) return;
        try {
          const word = await api<WordFull>(`/api/words/${wordId}/enrich`, "POST");
          if (cancelled) return;
          setCards((current) => current?.map((item) => (item.word.id === wordId ? { ...item, word } : item)) ?? null);
        } catch {
          return; // LLM indisponible : les cartes restent utilisables avec le dictionnaire
        }
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [batch, settings.auto_enrich]);

  const reveal = useCallback(() => {
    if (!card || revealed) return;
    setRevealed(true);
    if (card.kind !== "ecoute") void speak(card.word.simp, rate);
  }, [card, revealed, rate]);

  const answer = useCallback(
    async (rating: number) => {
      if (!card || !cards || busy) return;
      setBusy(true);
      setError("");
      try {
        const duration_ms = Math.min(Date.now() - shownAt.current, 600_000);
        await api(`/api/review/${card.id}`, "POST", { rating, duration_ms });
        setCanUndo(true);
        if (cards.length > 1) setCards(cards.slice(1));
        else await load();
      } catch (cause) {
        setError(errorMessage(cause));
      } finally {
        setBusy(false);
      }
    },
    [card, cards, busy, load],
  );

  async function undo() {
    setBusy(true);
    setError("");
    try {
      const restored = await api<Card>("/api/review/undo", "POST");
      setCards((current) => [restored, ...(current ?? []).filter((item) => item.id !== restored.id)]);
      setCanUndo(false);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.target instanceof HTMLInputElement || event.metaKey || event.ctrlKey) return;
      if (!revealed && (event.key === " " || event.key === "Enter")) {
        event.preventDefault();
        reveal();
      } else if (revealed && ["1", "2", "3", "4"].includes(event.key)) {
        void answer(Number(event.key));
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [revealed, reveal, answer]);

  if (!cards || !counts) return error ? <Notice tone="seal">{error}</Notice> : <Notice>Chargement…</Notice>;

  const undoButton = canUndo && (
    <button type="button" onClick={undo} disabled={busy} className="text-sm text-action underline">
      Annuler la dernière réponse
    </button>
  );

  if (!card) {
    const waiting = counts.new_backlog - counts.new;
    return (
      <div className="flex flex-col gap-4">
        <h1 className="text-2xl font-bold">Terminé pour l'instant</h1>
        <p>
          {waiting > 0
            ? `${waiting} mots attendent encore : la limite de nouvelles cartes du jour est atteinte.`
            : "Plus aucune carte à revoir ni à découvrir."}
        </p>
        {undoButton}
        {error && <Notice tone="seal">{error}</Notice>}
        <a href={waiting > 0 ? "#/" : "#/trier"} className="rounded-md bg-action px-4 py-3 text-center font-bold text-on-action">
          {waiting > 0 ? "Revenir à l'accueil" : "Ajouter des mots"}
        </a>
      </div>
    );
  }

  const word = card.word;
  const french = word.llm_fr || word.dict_fr || word.gloss_en;
  const typedRight = typed.trim() === word.simp;

  function submitTyped(event: FormEvent) {
    event.preventDefault();
    reveal();
  }

  return (
    <div className="flex flex-1 flex-col">
      <div className="mb-4 flex items-baseline justify-between text-sm text-soft">
        <span>
          {KIND_LABEL[card.kind]}
          {card.is_new && ", nouveau mot"}
        </span>
        <span>{cards.length === 1 ? "dernière carte" : `encore ${cards.length}`}</span>
      </div>

      {card.kind === "reco" && <Tian text={word.simp} />}

      {card.kind === "ecoute" && !revealed && (
        <div className="flex flex-col items-center gap-4 py-6">
          <Play text={word.simp} rate={rate} big label="Réécouter le mot" />
          <p className="text-soft">Que veut dire ce que tu entends ?</p>
          {sentence && (
            <button type="button" onClick={() => void speak(sentence.zh, rate)} className="text-action underline">
              L'entendre dans une phrase
            </button>
          )}
        </div>
      )}

      {card.kind === "prod" && !revealed && (
        <form onSubmit={submitTyped} className="flex flex-col gap-4 py-2">
          <p className="text-2xl">{french}</p>
          {sentence && (
            <div>
              <Zh className="block text-2xl">{sentence.zh.split(word.simp).join("＿＿")}</Zh>
              <p className="text-soft">{sentence.fr}</p>
            </div>
          )}
          <label className="flex flex-col gap-1 text-sm text-soft">
            Écris le mot en chinois
            <input
              lang="zh-Hans"
              autoFocus
              autoComplete="off"
              autoCapitalize="off"
              value={typed}
              onChange={(event) => setTyped(event.target.value)}
              className="min-h-14 rounded-md border border-line bg-sheet px-3 text-3xl text-ink"
            />
          </label>
        </form>
      )}

      {revealed && (
        <div className="reveal mt-5 flex flex-col gap-4">
          {card.kind !== "reco" && <Tian text={word.simp} />}
          {card.kind === "prod" && typed.trim() !== "" && (
            <p className={typedRight ? "text-action" : "text-seal"}>
              {typedRight ? "Exact." : <>Tu as écrit <Zh className="text-xl">{typed.trim()}</Zh>.</>}
            </p>
          )}
          <WordAnswer word={word} rate={rate} showEnglish={settings.show_english} sentenceIndex={sentenceIndex} />
        </div>
      )}

      <div className="sticky bottom-[calc(4.5rem+env(safe-area-inset-bottom))] mt-auto bg-paper pt-5 pb-2">
        {error && <Notice tone="seal">{error}</Notice>}
        {revealed ? (
          <div className="grid grid-cols-4 gap-2">
            {RATINGS.map((rating) => (
              <Button
                key={rating.value}
                tone={rating.tone}
                disabled={busy}
                onClick={() => void answer(rating.value)}
                className="flex flex-col items-center px-1 leading-tight"
              >
                <span>{rating.label}</span>
                <span className="text-xs font-normal opacity-80">{card.intervals[String(rating.value) as "1"]}</span>
              </Button>
            ))}
          </div>
        ) : (
          <Button tone="action" className="w-full" onClick={reveal}>
            {card.kind === "prod" ? "Vérifier" : "Voir la réponse"}
          </Button>
        )}
        <div className="mt-2 min-h-5 text-center">{undoButton}</div>
      </div>
    </div>
  );
}
