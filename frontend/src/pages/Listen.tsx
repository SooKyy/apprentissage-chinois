import { type FormEvent, useCallback, useEffect, useState } from "react";
import { api, errorMessage } from "../api";
import { speak, stop } from "../audio";
import type { ListenItem, Settings } from "../types";
import { Button, HAN, Notice, Play, Title, Zh } from "../ui";

const RATES = [0.6, 0.8, 1];

/** Marque chaque caractère attendu comme trouvé ou non, par plus longue sous-suite commune avec la saisie. */
export function compare(expected: string, typed: string): { char: string; ok: boolean }[] {
  const want = Array.from(expected);
  const got = Array.from(typed).filter((char) => HAN.test(char));
  const targets = want.map((char, index) => ({ char, index })).filter((item) => HAN.test(item.char));
  const table = Array.from({ length: targets.length + 1 }, () => new Array<number>(got.length + 1).fill(0));
  for (let i = targets.length - 1; i >= 0; i--) {
    for (let j = got.length - 1; j >= 0; j--) {
      table[i][j] = targets[i].char === got[j] ? table[i + 1][j + 1] + 1 : Math.max(table[i + 1][j], table[i][j + 1]);
    }
  }
  const matched = new Set<number>();
  for (let i = 0, j = 0; i < targets.length && j < got.length; ) {
    if (targets[i].char === got[j]) {
      matched.add(targets[i].index);
      i++;
      j++;
    } else if (table[i + 1][j] >= table[i][j + 1]) i++;
    else j++;
  }
  return want.map((char, index) => ({ char, ok: !HAN.test(char) || matched.has(index) }));
}

export function Listen({
  active,
  settings,
  save,
}: {
  active: boolean;
  settings: Settings;
  save: (changes: Partial<Settings>) => Promise<void>;
}) {
  const [items, setItems] = useState<ListenItem[] | null>(null);
  const [typed, setTyped] = useState("");
  const [checked, setChecked] = useState(false);
  const [error, setError] = useState("");
  const rate = settings.tts_rate;

  const load = useCallback(async () => {
    setItems(await api<ListenItem[]>("/api/listen?limit=10"));
  }, []);

  // Chargé dès le démarrage. Tant qu'il n'y a aucune phrase, on redemande à chaque retour sur l'onglet :
  // les révisions en ajoutent
  const loaded = items !== null;
  const empty = !items?.length;
  useEffect(() => {
    if (empty && (active || !loaded)) load().catch((cause) => setError(errorMessage(cause)));
    if (active) return stop;
  }, [active, empty, loaded, load]);

  const item = items?.[0];

  async function next() {
    setTyped("");
    setChecked(false);
    try {
      if (items && items.length > 1) {
        setItems(items.slice(1));
        void speak(items[1].zh, rate);
      } else await load();
    } catch (cause) {
      setError(errorMessage(cause));
    }
  }

  function check(event: FormEvent) {
    event.preventDefault();
    setChecked(true);
  }

  const result = item && checked ? compare(item.zh, typed) : null;
  const missed = result ? result.filter((part) => !part.ok).length : 0;

  return (
    <div className="flex flex-1 flex-col">
      <Title>Écouter</Title>
      {error && <Notice tone="seal">{error}</Notice>}
      {!items ? (
        !error && <Notice>Chargement…</Notice>
      ) : !item ? (
        <div className="flex flex-col gap-4">
          <p>
            Pas encore de phrase à écouter. Elles viennent des mots que tu apprends : elles s'ajoutent toutes seules
            pendant tes révisions.
          </p>
          <a href="#/trier" className="rounded-md bg-action px-4 py-3 text-center font-bold text-on-action">
            Choisir des mots
          </a>
        </div>
      ) : (
        <>
          <div className="flex flex-col items-center gap-4 py-2">
            <Play text={item.zh} rate={rate} big label="Écouter la phrase" />
            <div className="flex gap-2" role="group" aria-label="Vitesse de lecture">
              {RATES.map((value) => (
                <button
                  key={value}
                  type="button"
                  aria-pressed={rate === value}
                  onClick={() => void save({ tts_rate: value })}
                  className={`min-h-10 rounded-md border px-3 text-sm ${
                    rate === value ? "border-action bg-action text-on-action" : "border-line bg-sheet"
                  }`}
                >
                  {value === 1 ? "Vitesse normale" : `${value} ×`}
                </button>
              ))}
            </div>
          </div>

          <form onSubmit={check} className="mt-4 flex flex-col gap-3">
            <label className="flex flex-col gap-1 text-sm text-soft">
              Écris ce que tu entends, ou réponds dans ta tête
              <input
                lang="zh-Hans"
                autoComplete="off"
                autoCapitalize="off"
                value={typed}
                disabled={checked}
                onChange={(event) => setTyped(event.target.value)}
                className="min-h-14 rounded-md border border-line bg-sheet px-3 text-2xl text-ink"
              />
            </label>
            {!checked && (
              <Button type="submit" tone="action">
                {typed.trim() ? "Vérifier" : "Voir la phrase"}
              </Button>
            )}
          </form>

          {result && (
            <div className="reveal mt-4 flex flex-col gap-2">
              <p lang="zh-Hans" className="text-3xl leading-snug">
                {result.map((part, index) => (
                  <span key={index} className={part.ok || !typed.trim() ? "" : "text-seal underline"}>
                    {part.char}
                  </span>
                ))}
              </p>
              <p className="text-soft">{item.pinyin}</p>
              <p className="text-lg">{item.fr}</p>
              {typed.trim() && (
                <p className={missed ? "text-seal" : "text-action"}>
                  {missed ? `${missed} caractère${missed > 1 ? "s" : ""} à revoir, soulignés en rouge.` : "Tout est juste."}
                </p>
              )}
              <p className="text-sm text-soft">
                Phrase du mot <Zh className="text-base text-ink">{item.word.simp}</Zh> ({item.word.pinyin})
              </p>
            </div>
          )}

          {checked && (
            <div className="sticky bottom-[calc(4.5rem+env(safe-area-inset-bottom))] mt-auto bg-paper pt-5 pb-2">
              <Button tone="action" className="w-full" onClick={() => void next()}>
                Phrase suivante
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
