import { readFile } from "node:fs/promises";
import path from "node:path";

import type { BookChapter } from "@/types/book";

export const bookTitle = "Когда кофе и капуста конкурируют";
export const bookDescription =
  "Русский перевод книги Alan Klement «When Coffee and Kale Compete» в удобной веб-читалке.";

const chapterMeta = [
  { file: "00_translator_note.md", label: "T", kind: "От переводчика" },
  { file: "00_foreword.md", label: "00", kind: "Вступление" },
  { file: "00_acknowledgments.md", label: "00", kind: "Вступление" },
  { file: "01_chapter.md", label: "01", kind: "Часть I" },
  { file: "02_chapter.md", label: "02", kind: "Часть I" },
  { file: "03_chapter.md", label: "03", kind: "Часть I" },
  { file: "04_chapter.md", label: "04", kind: "Кейс" },
  { file: "05_chapter.md", label: "05", kind: "Кейс" },
  { file: "06_chapter.md", label: "06", kind: "Часть II" },
  { file: "07_chapter.md", label: "07", kind: "Часть II" },
  { file: "08_chapter.md", label: "08", kind: "Кейс" },
  { file: "09_chapter.md", label: "09", kind: "Кейс" },
  { file: "10_chapter.md", label: "10", kind: "Кейс" },
  { file: "11_chapter.md", label: "11", kind: "Часть III" },
  { file: "12_chapter.md", label: "12", kind: "Часть III" },
  { file: "13_chapter.md", label: "13", kind: "Практика" },
  { file: "14_chapter.md", label: "14", kind: "Финал" },
  { file: "15_appendix.md", label: "A15", kind: "Приложение" },
  { file: "16_appendix.md", label: "A16", kind: "Приложение" },
  { file: "17_appendix.md", label: "A17", kind: "Приложение" },
  { file: "18_notes.md", label: "N18", kind: "Примечания" }
] as const;

export async function getBookChapters(): Promise<BookChapter[]> {
  const translatedDir = path.join(process.cwd(), "translated");

  return Promise.all(
    chapterMeta.map(async (chapter, index) => {
      const raw = await readFile(path.join(translatedDir, chapter.file), "utf8");
      const title = raw.match(/^#\s+(.+)$/m)?.[1] || chapter.file;

      return {
        ...chapter,
        index,
        raw,
        title,
        words: countWords(raw)
      };
    })
  );
}

function countWords(value: string): number {
  return (value.match(/[A-Za-zА-Яа-яЁё0-9-]+/g) || []).length;
}
