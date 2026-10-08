import { useEffect, useState } from "react";
import { api, errorMessage } from "../api";
import type { Stats } from "../types";
import { Meter, Notice, Title } from "../ui";

const plural = (count: number, one: string, many: string) => `${count} ${count === 1 ? one : many}`;

export function Today({ active }: { active: boolean }) {
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState("");

  // À chaque retour sur l'onglet : les anciens chiffres restent affichés pendant la mise à jour
  useEffect(() => {
    if (!active) return;
    api<Stats>("/api/stats")
      .then((fresh) => {
        setStats(fresh);
        setError("");
      })
      .catch((cause) => setError(errorMessage(cause)));
  }, [active]);

  if (!stats) return error ? <Notice tone="seal">{error}</Notice> : <Notice>Chargement…</Notice>;

  const { due, new: fresh, new_backlog } = stats.queue;
  const todo = due + fresh;
  const empty = stats.words.learning === 0;

  return (
    <>
      <Title
        aside={
          <a href="#/reglages" className="text-sm text-action underline">
            Réglages
          </a>
        }
      >
        Aujourd'hui
      </Title>
      {error && <Notice tone="seal">{error}</Notice>}

      <section className="mb-8">
        {empty ? (
          <>
            <p className="mb-4 text-lg">Aucun mot à apprendre pour l'instant.</p>
            <a href="#/trier" className="block rounded-md bg-action px-4 py-3 text-center font-bold text-on-action">
              Choisir mes premiers mots
            </a>
          </>
        ) : (
          <>
            <p className="mb-1 text-lg">
              {todo === 0
                ? "Tout est révisé."
                : `${plural(due, "carte à revoir", "cartes à revoir")}, ${plural(fresh, "nouvelle", "nouvelles")}.`}
            </p>
            <p className="mb-4 text-sm text-soft">
              {plural(stats.reviews_today, "réponse", "réponses")} aujourd'hui
              {stats.streak > 0 && `, ${plural(stats.streak, "jour", "jours")} d'affilée`}
              {stats.retention_30d !== null && `, ${Math.round(stats.retention_30d * 100)} % retenu sur 30 jours`}.
            </p>
            {todo > 0 ? (
              <a href="#/session" className="block rounded-md bg-action px-4 py-3 text-center font-bold text-on-action">
                Réviser
              </a>
            ) : (
              new_backlog === 0 && (
                <a href="#/trier" className="block rounded-md border border-line bg-sheet px-4 py-3 text-center">
                  Ajouter des mots
                </a>
              )
            )}
          </>
        )}
      </section>

      <section className="mb-8">
        <h2 className="mb-1 text-lg font-bold">Mots les plus fréquents</h2>
        <p className="mb-4 text-sm text-soft">
          Ce que tu sais déjà parmi les mots qui reviennent le plus. Les trous ici sont le petit vocabulaire qui te manque.
        </p>
        <ul className="flex flex-col gap-3">
          {stats.coverage.map((step) => {
            const sorted = step.known + step.learning + step.ignored;
            return (
              <li key={step.top}>
                <div className="mb-1 flex justify-between text-sm">
                  <span>Les {step.top.toLocaleString("fr-FR")} premiers</span>
                  <span className="text-soft">
                    {step.known} connus, {step.learning} en cours, {step.total - sorted} à trier
                  </span>
                </div>
                <Meter
                  total={step.total}
                  label={`${step.known} connus et ${step.learning} en cours sur ${step.total}`}
                  parts={[
                    { value: step.known, className: "bg-action" },
                    { value: step.learning, className: "bg-grid opacity-50" },
                  ]}
                />
              </li>
            );
          })}
        </ul>
      </section>

      <section>
        <h2 className="mb-2 text-lg font-bold">À venir</h2>
        <ul className="grid grid-cols-7 gap-1 text-center text-sm">
          {stats.forecast.map((day) => (
            <li key={day.day} className="rounded-md border border-line bg-sheet py-2">
              <div className="text-soft">
                {new Date(`${day.day}T12:00:00`).toLocaleDateString("fr-FR", { weekday: "short" }).replace(".", "")}
              </div>
              <div className="font-bold">{day.due}</div>
            </li>
          ))}
        </ul>
        <p className="mt-3 text-sm text-soft">
          {stats.words.known} mots connus, {stats.words.learning} en cours.
        </p>
      </section>
    </>
  );
}
