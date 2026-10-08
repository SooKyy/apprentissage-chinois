import { type FormEvent, useState } from "react";
import { api, errorMessage, setToken } from "../api";
import { Button, Notice, Tian } from "../ui";

export function Login() {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const { access_token } = await api<{ access_token: string }>("/api/auth/login", "POST", { password });
      setToken(access_token);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="mx-auto flex min-h-dvh max-w-sm flex-col justify-center gap-5 p-6">
      <Tian text="学习" />
      <label className="flex flex-col gap-1">
        Mot de passe
        <input
          type="password"
          autoComplete="current-password"
          autoFocus
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          className="min-h-12 rounded-md border border-line bg-sheet px-3"
        />
      </label>
      {error && <Notice tone="seal">{error}</Notice>}
      <Button type="submit" tone="action" disabled={busy}>
        Se connecter
      </Button>
    </form>
  );
}
