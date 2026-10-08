import { apiBlob } from "./api";

// Un seul lecteur réutilisé : une fois débloqué par un geste, iOS le laisse rejouer sans nouveau geste.
const player = new Audio();
const clips = new Map<string, Promise<string>>();

export function preload(text: string): Promise<string> {
  let clip = clips.get(text);
  if (!clip) {
    clip = apiBlob(`/api/tts?text=${encodeURIComponent(text)}`).then((blob) => URL.createObjectURL(blob));
    clip.catch(() => clips.delete(text));
    clips.set(text, clip);
  }
  return clip;
}

/** Lit le texte chinois. Rend false si la lecture a échoué (réseau, ou lecture auto refusée par le navigateur). */
export async function speak(text: string, rate = 1): Promise<boolean> {
  try {
    const url = await preload(text);
    player.pause();
    player.src = url;
    player.defaultPlaybackRate = rate;
    player.playbackRate = rate;
    await player.play();
    return true;
  } catch {
    return false;
  }
}

export function stop() {
  player.pause();
}
