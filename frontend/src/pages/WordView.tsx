import type { Sentence, WordFull } from "../types";
import { Play, Zh } from "../ui";

export function SentenceLine({ sentence, rate, hideZh = false }: { sentence: Sentence; rate: number; hideZh?: boolean }) {
  return (
    <div className="flex items-start gap-3">
      <Play text={sentence.zh} rate={rate} label="Écouter la phrase" />
      <div className="min-w-0">
        {!hideZh && <Zh className="block text-2xl leading-snug">{sentence.zh}</Zh>}
        {!hideZh && <div className="text-sm text-soft">{sentence.pinyin}</div>}
        <div>{sentence.fr}</div>
      </div>
    </div>
  );
}

/** Tout ce qu'on sait d'un mot : lectures, sens, note d'usage, phrases. Le caractère lui-même est affiché par l'appelant. */
export function WordAnswer({
  word,
  rate,
  showEnglish,
  sentenceIndex,
}: {
  word: WordFull;
  rate: number;
  showEnglish: boolean;
  sentenceIndex?: number;
}) {
  const french = word.llm_fr || word.dict_fr;
  const sentences =
    sentenceIndex === undefined ? word.sentences : word.sentences.slice(sentenceIndex, sentenceIndex + 1);
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-3">
        <Play text={word.simp} rate={rate} />
        <div>
          <div className="text-2xl">{word.pinyin}</div>
          {word.trad !== word.simp && (
            <div className="text-sm text-soft">
              traditionnel <Zh>{word.trad}</Zh>
            </div>
          )}
        </div>
      </div>
      <div>
        {french && <p className="text-xl">{french}</p>}
        {(showEnglish || !french) && <p className="text-soft">{word.gloss_en}</p>}
      </div>
      {word.readings.length > 1 && (
        <ul className="border-l-2 border-line pl-3 text-sm">
          {word.readings.map((reading) => (
            <li key={reading.num}>
              <span className="font-bold">{reading.pinyin}</span>{" "}
              <span className="text-soft">{(reading.fr.length ? reading.fr : reading.en).slice(0, 3).join(", ")}</span>
            </li>
          ))}
        </ul>
      )}
      {sentences.map((sentence) => (
        <SentenceLine key={sentence.id} sentence={sentence} rate={rate} />
      ))}
      {word.llm_note && <p className="text-sm text-soft">{word.llm_note}</p>}
    </div>
  );
}
