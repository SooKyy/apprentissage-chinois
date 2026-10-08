export type Status = "learning" | "known" | "ignored";
export type Kind = "reco" | "ecoute" | "prod";

export interface Sentence {
  id: number;
  zh: string;
  pinyin: string;
  fr: string;
}

export interface WordBrief {
  id: number;
  simp: string;
  trad: string;
  pinyin: string;
  gloss_fr: string | null;
  gloss_en: string;
  hsk: number | null;
  freq_rank: number | null;
  status: Status | null;
}

export interface Reading {
  pinyin: string;
  num: string;
  trad: string;
  en: string[];
  fr: string[];
}

export interface WordFull extends WordBrief {
  readings: Reading[];
  dict_fr: string | null;
  llm_fr: string | null;
  llm_note: string | null;
  enriched: boolean;
  sentences: Sentence[];
}

export interface Card {
  id: number;
  kind: Kind;
  is_new: boolean;
  state: number | null;
  reps: number;
  lapses: number;
  intervals: Record<"1" | "2" | "3" | "4", string>;
  word: WordFull;
}

export interface QueueCounts {
  due: number;
  new: number;
  new_backlog: number;
  introduced_today: number;
}

export interface Queue {
  counts: QueueCounts;
  cards: Card[];
}

export interface Coverage {
  top: number;
  total: number;
  known: number;
  learning: number;
  ignored: number;
}

export interface Stats {
  queue: QueueCounts;
  words: Record<Status, number>;
  reviews_today: number;
  streak: number;
  retention_30d: number | null;
  history: { day: string; reviews: number }[];
  coverage: Coverage[];
  forecast: { day: string; due: number }[];
}

export interface Settings {
  new_per_day: number;
  desired_retention: number;
  card_kinds: Kind[];
  auto_enrich: boolean;
  tts_rate: number;
  show_english: boolean;
}

export interface PlacementResult {
  estimate: number;
  out_of: number;
  bands: { from: number; to: number; tested: number; known: number; ratio: number }[];
  suggested_after_rank: number;
}

export interface Explanation {
  texte: string;
  pinyin: string;
  traduction: string;
  litteral: string;
  mots: { zh: string; sens: string; pinyin: string; word_id: number | null; status: Status | null }[];
  grammaire: { point: string; explication: string }[];
  registre: string;
}

export interface Correction {
  original: string;
  correct: boolean;
  corrige: string;
  corrige_pinyin: string;
  naturel: string;
  naturel_pinyin: string;
  traduction: string;
  erreurs: { original: string; correction: string; explication: string }[];
}

export interface ListenItem extends Sentence {
  word: WordBrief;
}
