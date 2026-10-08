import { useCallback, useEffect, useState } from "react";
import { api, errorMessage } from "../api";
import type { PlacementResult, Status, WordBrief } from "../types";
import { Button, Meter, Notice, Play, Tian, Title } from "../ui";

const START_KEY = "chinois.tri.rang";
const BATCH = 40;

function WordFace({ word, shown, onShow }: { word: WordBrief; shown: boolean; onShow: () => void }) {
  return (
    <div className="flex flex-col items-center gap-4">
      <Tian text={word.simp} />
      {shown ? (
        <div className="reveal flex w-full items-center gap-3">
          <Play text={word.simp} />
          <div className="min-w-0">
            <div className="text-xl">{word.pinyin}</div>
            <div>{word.gloss_fr || word.gloss_en}</div>
          </div>
        </div>
      ) : (
        <button type="button" onClick={onShow} className="min-h-12 text-action underline">
          Voir le sens
        </button>
      )}
    </div>
  );
}

function Placement({ onDone }: { onDone: (afterRank: number | null) => void }) {
  const [words, setWords] = useState<WordBrief[] | null>(null);
  const [answers, setAnswers] = useState<{ word_id: number; known: boolean }[]>([]);
  const [shown, setShown] = useState(false);
  const [result, setResult] = useState<PlacementResult | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<WordBrief[]>("/api/placement")
      .then(setWords)
      .catch((cause) => setError(errorMessage(cause)));
  }, []);

  async function reply(known: boolean) {
    if (!words) return;
    const next = [...answers, { word_id: words[answers.length].id, known }];
    setAnswers(next);
    setShown(false);
    if (next.length === words.length) {
      try {
        setResult(await api<PlacementResult>("/api/placement", "POST", { answers: next }));
      } catch (cause) {
        setError(errorMessage(cause));
      }
    }
  }

  if (error) return <Notice tone="seal">{error}</Notice>;
  if (!words) return <Notice>Chargement…</Notice>;

  if (result) {
    return (
      <div className="flex flex-col gap-4">
        <Title>Ton niveau estimé</Title>
        <p className="text-lg">
          Tu connais environ {result.estimate} des {result.out_of} mots les plus fréquents.
        </p>
        <ul className="flex flex-col gap-3">
          {result.bands.map((band) => (
            <li key={band.from}>
              <div className="mb-1 flex justify-between text-sm">
                <span>
                  Rangs {band.from} à {band.to}
                </span>
                <span className="text-soft">
                  {band.known} sur {band.tested}
                </span>
              </div>
              <Meter total={band.tested} label={`${band.known} connus sur ${band.tested}`} parts={[{ value: band.known, className: "bg-action" }]} />
            </li>
          ))}
        </ul>
        <Notice>Les mots que tu as reconnus sont notés comme connus. Les autres restent à trier.</Notice>
        <Button tone="action" onClick={() => onDone(result.suggested_after_rank)}>
          Trier à partir du rang {result.suggested_after_rank + 1}
        </Button>
        <Button onClick={() => onDone(0)}>Trier depuis le début, pour trouver les trous</Button>
      </div>
    );
  }

  const word = words[answers.length];
  if (!word) return <Notice>Calcul…</Notice>;
  return (
    <div className="flex flex-1 flex-col gap-5">
      <div className="flex items-baseline justify-between text-sm text-soft">
        <span>
          Mot {answers.length + 1} sur {words.length}
        </span>
        <button type="button" onClick={() => onDone(null)} className="text-action underline">
          Arrêter
        </button>
      </div>
      <WordFace word={word} shown={shown} onShow={() => setShown(true)} />
      <div className="mt-auto grid grid-cols-2 gap-2">
        <Button onClick={() => void reply(false)}>Je ne connais pas</Button>
        <Button tone="action" onClick={() => void reply(true)}>
          Je connais
        </Button>
      </div>
    </div>
  );
}

export function Triage() {
  const [afterRank, setAfterRank] = useState(() => Number(localStorage.getItem(START_KEY)) || 0);
  const [hsk, setHsk] = useState(0);
  const [words, setWords] = useState<WordBrief[] | null>(null);
  const [remaining, setRemaining] = useState(0);
  const [shown, setShown] = useState(false);
  const [last, setLast] = useState<WordBrief | null>(null);
  const [added, setAdded] = useState(0);
  const [placement, setPlacement] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    const query = new URLSearchParams({ limit: String(BATCH), after_rank: String(hsk ? 0 : afterRank) });
    if (hsk) query.set("hsk", String(hsk));
    const data = await api<{ remaining: number; words: WordBrief[] }>(`/api/triage?${query}`);
    setWords(data.words);
    setRemaining(data.remaining);
  }, [afterRank, hsk]);

  useEffect(() => {
    if (placement) return;
    setWords(null);
    load().catch((cause) => setError(errorMessage(cause)));
  }, [load, placement]);

  if (placement) {
    return (
      <Placement
        onDone={(rank) => {
          if (rank !== null) {
            localStorage.setItem(START_KEY, String(rank));
            setAfterRank(rank);
            setHsk(0);
          }
          setPlacement(false);
        }}
      />
    );
  }

  const word = words?.[0];

  async function sort(status: Status) {
    if (!word || !words) return;
    setError("");
    try {
      await api(`/api/words/${word.id}/status`, "PUT", { status, source: "tri" });
      setLast(word);
      if (status === "learning") setAdded((value) => value + 1);
      setShown(false);
      setRemaining((value) => value - 1);
      if (words.length > 1) setWords(words.slice(1));
      else await load();
    } catch (cause) {
      setError(errorMessage(cause));
    }
  }

  async function undo() {
    if (!last) return;
    try {
      await api(`/api/words/${last.id}/status`, "DELETE");
      setWords((current) => [last, ...(current ?? [])]);
      setRemaining((value) => value + 1);
      setLast(null);
      setShown(false);
    } catch (cause) {
      setError(errorMessage(cause));
    }
  }

  return (
    <div className="flex flex-1 flex-col">
      <Title
        aside={
          <button type="button" onClick={() => setPlacement(true)} className="text-sm text-action underline">
            Estimer mon niveau
          </button>
        }
      >
        Trier
      </Title>
      <div className="mb-5 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
        <label className="flex items-center gap-2">
          Liste
          <select
            value={hsk}
            onChange={(event) => setHsk(Number(event.target.value))}
            className="min-h-10 rounded-md border border-line bg-sheet px-2"
          >
            <option value={0}>Par fréquence</option>
            {[1, 2, 3, 4, 5, 6].map((level) => (
              <option key={level} value={level}>
                HSK {level}
              </option>
            ))}
            <option value={7}>HSK 7 à 9</option>
          </select>
        </label>
        <span className="text-soft">
          {remaining.toLocaleString("fr-FR")} à trier{added > 0 && `, ${added} ajoutés`}
        </span>
      </div>

      {error && <Notice tone="seal">{error}</Notice>}
      {!words ? (
        <Notice>Chargement…</Notice>
      ) : !word ? (
        <p>Tous les mots de cette liste sont triés.</p>
      ) : (
        <>
          <WordFace word={word} shown={shown} onShow={() => setShown(true)} />
          <p className="mt-3 text-center text-sm text-soft">
            {word.freq_rank && `${word.freq_rank}ᵉ mot le plus fréquent`}
            {word.freq_rank && word.hsk ? ", " : ""}
            {word.hsk ? (word.hsk === 7 ? "HSK 7 à 9" : `HSK ${word.hsk}`) : ""}
          </p>
          <div className="sticky bottom-[calc(4.5rem+env(safe-area-inset-bottom))] mt-auto bg-paper pt-5 pb-2">
            <div className="grid grid-cols-2 gap-2">
              <Button onClick={() => void sort("known")}>Je connais</Button>
              <Button tone="action" onClick={() => void sort("learning")}>
                Apprendre
              </Button>
            </div>
            <div className="mt-2 flex min-h-5 justify-between text-sm">
              <button type="button" onClick={() => void sort("ignored")} className="text-soft underline">
                Ne pas apprendre ce mot
              </button>
              {last && (
                <button type="button" onClick={() => void undo()} className="text-action underline">
                  Annuler {last.simp}
                </button>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
