import { useCallback, useEffect, useState } from "react";
import { api, errorMessage, getToken } from "./api";
import { Assist } from "./pages/Assist";
import { Listen } from "./pages/Listen";
import { Login } from "./pages/Login";
import { Review } from "./pages/Review";
import { Search } from "./pages/Search";
import { SettingsPage } from "./pages/Settings";
import { Today } from "./pages/Today";
import { Triage } from "./pages/Triage";
import type { Settings } from "./types";
import { Notice, Zh } from "./ui";

const TABS = [
  { path: "", han: "习", label: "Réviser" },
  { path: "trier", han: "选", label: "Trier" },
  { path: "ecouter", han: "听", label: "Écouter" },
  { path: "chercher", han: "查", label: "Chercher" },
  { path: "aide", han: "问", label: "Demander" },
];

const currentPath = () => window.location.hash.replace(/^#\/?/, "");

export function App() {
  const [authed, setAuthed] = useState(() => getToken() !== null);
  const [path, setPath] = useState(currentPath);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const onAuth = () => setAuthed(getToken() !== null);
    const onHash = () => setPath(currentPath());
    window.addEventListener("auth-changed", onAuth);
    window.addEventListener("hashchange", onHash);
    return () => {
      window.removeEventListener("auth-changed", onAuth);
      window.removeEventListener("hashchange", onHash);
    };
  }, []);

  useEffect(() => {
    if (!authed) return;
    api<Settings>("/api/settings")
      .then(setSettings)
      .catch((cause) => setError(errorMessage(cause)));
  }, [authed]);

  useEffect(() => window.scrollTo(0, 0), [path]);

  const saveSettings = useCallback(async (changes: Partial<Settings>) => {
    // Affichage immédiat, puis valeur confirmée par le serveur (ou retour en arrière s'il refuse)
    setSettings((current) => current && { ...current, ...changes });
    try {
      setSettings(await api<Settings>("/api/settings", "PUT", changes));
    } catch (cause) {
      setSettings(await api<Settings>("/api/settings"));
      throw cause;
    }
  }, []);

  if (!authed) return <Login />;
  if (!settings) {
    return <div className="p-6">{error ? <Notice tone="seal">{error}</Notice> : <Notice>Chargement…</Notice>}</div>;
  }

  const section = path.split("/")[0];
  const tab = TABS.some((item) => item.path === section) ? section : "";
  const overlay = path === "reglages" || path === "session";

  return (
    <div className="mx-auto flex min-h-dvh max-w-[30rem] flex-col">
      <main className="flex flex-1 flex-col px-4 pt-6 pb-[calc(5.5rem+env(safe-area-inset-bottom))]">
        {path === "reglages" && <SettingsPage settings={settings} save={saveSettings} />}
        {path === "session" && <Review settings={settings} />}
        {/* Les onglets restent montés : on y revient sans rechargement, là où on s'était arrêté */}
        {TABS.map((item) => {
          const active = !overlay && item.path === tab;
          return (
            <div key={item.path} className={active ? "flex flex-1 flex-col" : "hidden"}>
              {item.path === "trier" ? (
                <Triage />
              ) : item.path === "ecouter" ? (
                <Listen active={active} settings={settings} save={saveSettings} />
              ) : item.path === "chercher" ? (
                <Search active={active} settings={settings} />
              ) : item.path === "aide" ? (
                <Assist />
              ) : (
                <Today active={active} />
              )}
            </div>
          );
        })}
      </main>
      <nav
        aria-label="Sections"
        className="fixed inset-x-0 bottom-0 z-10 border-t border-line bg-sheet pb-[env(safe-area-inset-bottom)]"
      >
        <ul className="mx-auto flex max-w-[30rem]">
          {TABS.map((item) => {
            const active = path !== "reglages" && (item.path === tab || (item.path === "" && path === "session"));
            return (
              <li key={item.path} className="flex-1">
                <a
                  href={`#/${item.path}`}
                  aria-current={active ? "page" : undefined}
                  className={`flex flex-col items-center gap-0.5 py-2 text-xs ${active ? "text-action" : "text-soft"}`}
                >
                  <Zh className={`text-2xl leading-none ${active ? "font-bold" : ""}`}>{item.han}</Zh>
                  {item.label}
                </a>
              </li>
            );
          })}
        </ul>
      </nav>
    </div>
  );
}
