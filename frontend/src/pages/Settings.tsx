import { useState } from "react";
import { errorMessage, setToken } from "../api";
import type { Kind, Settings } from "../types";
import { Button, Notice, Title } from "../ui";

const KINDS: { value: Kind; label: string; hint: string }[] = [
  { value: "reco", label: "Lecture", hint: "tu vois le mot, tu retrouves le sens et la prononciation" },
  { value: "ecoute", label: "Écoute", hint: "tu entends le mot, tu retrouves le sens" },
  { value: "prod", label: "Écriture", hint: "tu vois le sens, tu tapes le mot en chinois" },
];

export function SettingsPage({ settings, save }: { settings: Settings; save: (changes: Partial<Settings>) => Promise<void> }) {
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  async function change(changes: Partial<Settings>) {
    setError("");
    setSaved(false);
    try {
      await save(changes);
      setSaved(true);
    } catch (cause) {
      setError(errorMessage(cause));
    }
  }

  function toggleKind(kind: Kind) {
    const kinds = settings.card_kinds.includes(kind)
      ? settings.card_kinds.filter((item) => item !== kind)
      : [...settings.card_kinds, kind];
    if (kinds.length === 0) {
      setError("Garde au moins un type de carte.");
      return;
    }
    void change({ card_kinds: kinds });
  }

  return (
    <div className="flex flex-col gap-6">
      <Title
        aside={
          <a href="#/" className="text-sm text-action underline">
            Retour
          </a>
        }
      >
        Réglages
      </Title>

      <label className="flex flex-col gap-1">
        Nouvelles cartes par jour
        <select
          value={settings.new_per_day}
          onChange={(event) => void change({ new_per_day: Number(event.target.value) })}
          className="min-h-12 rounded-md border border-line bg-sheet px-3"
        >
          {[...new Set([0, 6, 8, 10, 12, 16, 20, 30, 40, settings.new_per_day])]
            .sort((a, b) => a - b)
            .map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
        </select>
        <span className="text-sm text-soft">
          Chaque mot donne une carte par type coché ci-dessous, présentées sur des jours différents. Compte environ dix
          fois ce nombre en révisions quotidiennes au bout de quelques semaines.
        </span>
      </label>

      <fieldset className="flex flex-col gap-2">
        <legend className="mb-1">Types de cartes pour les nouveaux mots</legend>
        {KINDS.map((kind) => (
          <label key={kind.value} className="flex items-start gap-3">
            <input
              type="checkbox"
              checked={settings.card_kinds.includes(kind.value)}
              onChange={() => toggleKind(kind.value)}
              className="mt-1 h-5 w-5 accent-[var(--action)]"
            />
            <span>
              {kind.label}
              <span className="block text-sm text-soft">{kind.hint}</span>
            </span>
          </label>
        ))}
        <span className="text-sm text-soft">Ne change rien aux mots déjà ajoutés.</span>
      </fieldset>

      <label className="flex flex-col gap-1">
        Part des cartes dont tu veux te souvenir
        <select
          value={settings.desired_retention}
          onChange={(event) => void change({ desired_retention: Number(event.target.value) })}
          className="min-h-12 rounded-md border border-line bg-sheet px-3"
        >
          {[0.8, 0.85, 0.9, 0.93, 0.95].map((value) => (
            <option key={value} value={value}>
              {Math.round(value * 100)} %
            </option>
          ))}
        </select>
        <span className="text-sm text-soft">Plus c'est haut, plus les révisions sont rapprochées. 90 % est un bon équilibre.</span>
      </label>

      <label className="flex items-start gap-3">
        <input
          type="checkbox"
          checked={settings.auto_enrich}
          onChange={(event) => void change({ auto_enrich: event.target.checked })}
          className="mt-1 h-5 w-5 accent-[var(--action)]"
        />
        <span>
          Phrases d'exemple automatiques
          <span className="block text-sm text-soft">
            Pendant les révisions, le modèle DeepSeek ajoute un sens français court et trois phrases aux mots qui n'en
            ont pas. Seul le mot lui est envoyé.
          </span>
        </span>
      </label>

      <label className="flex items-start gap-3">
        <input
          type="checkbox"
          checked={settings.show_english}
          onChange={(event) => void change({ show_english: event.target.checked })}
          className="mt-1 h-5 w-5 accent-[var(--action)]"
        />
        <span>
          Afficher aussi le sens en anglais
          <span className="block text-sm text-soft">Le dictionnaire anglais est plus complet que le français.</span>
        </span>
      </label>

      {error && <Notice tone="seal">{error}</Notice>}
      {saved && <Notice>Réglage enregistré.</Notice>}

      <Button onClick={() => setToken(null)}>Se déconnecter</Button>
    </div>
  );
}
