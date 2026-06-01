import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

const root = process.cwd();
const readerDir = path.join(root, "reader");
const figureDir = path.join(readerDir, "images");
const translatedDir = path.join(root, "translated");
const outDir = path.join(root, "dist");
const outFile = "when-coffee-and-kale-compete-ru.html";
const figureCount = 36;

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
];

const [html, css, js, cover] = await Promise.all([
  readFile(path.join(readerDir, "index.html"), "utf8"),
  readFile(path.join(readerDir, "styles.css"), "utf8"),
  readFile(path.join(readerDir, "app.js"), "utf8"),
  readFile(path.join(readerDir, "cover.png"))
]);

const chapters = await Promise.all(
  chapterMeta.map(async (chapter) => {
    const raw = await readFile(path.join(translatedDir, chapter.file), "utf8");
    const title = (raw.match(/^#\s+(.+)$/m) || [null, chapter.file])[1];
    const words = countWords(raw);
    return { ...chapter, raw, title, words };
  })
);

const embeddedChapters = JSON.stringify(chapters).replace(/</g, "\\u003c");
const embeddedFigureMap = JSON.stringify(await buildFigureImageMap()).replace(/</g, "\\u003c");
const coverData = `data:image/png;base64,${cover.toString("base64")}`;

const standalone = html
  .replace('<link rel="stylesheet" href="./styles.css">', () => `<style>\n${css}\n</style>`)
  .replace('src="./cover.png"', () => `src="${coverData}"`)
  .replace('<script src="./app.js"></script>', () => `<script>\nwindow.EMBEDDED_CHAPTERS = ${embeddedChapters};\nwindow.FIGURE_IMAGE_MAP = ${embeddedFigureMap};\n</script>\n<script>\n${js}\n</script>`)
  .replace("</title>", () => " · один файл</title>")
  .replace("</head>", () => '<meta name="description" content="Автономная HTML-читалка перевода книги When Coffee and Kale Compete.">\n  </head>');

await mkdir(outDir, { recursive: true });
await writeFile(path.join(outDir, outFile), standalone, "utf8");

console.log(`Built dist/${outFile} (${formatBytes(Buffer.byteLength(standalone))})`);

function countWords(value) {
  return (value.match(/[A-Za-zА-Яа-яЁё0-9-]+/g) || []).length;
}

function formatBytes(bytes) {
  const units = ["B", "KB", "MB"];
  let size = bytes;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  return `${size.toFixed(size >= 10 || unit === 0 ? 0 : 1)} ${units[unit]}`;
}

async function buildFigureImageMap() {
  const map = {};
  for (let figure = 1; figure <= figureCount; figure += 1) {
    const imageName = `imageFile${figure + 1}.png`;
    const image = await readFile(path.join(figureDir, imageName));
    map[String(figure)] = `data:image/png;base64,${image.toString("base64")}`;
  }
  return map;
}
