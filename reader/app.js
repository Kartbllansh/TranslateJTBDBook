const chapters = window.EMBEDDED_CHAPTERS || [
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

const figureImageMap = window.FIGURE_IMAGE_MAP || createDefaultFigureImageMap();

const els = {
  chapterList: document.querySelector("#chapterList"),
  sectionRail: document.querySelector("#sectionRail"),
  content: document.querySelector("#content"),
  searchInput: document.querySelector("#searchInput"),
  currentKicker: document.querySelector("#currentKicker"),
  currentTitle: document.querySelector("#currentTitle"),
  readProgress: document.querySelector("#readProgress"),
  prevChapter: document.querySelector("#prevChapter"),
  nextChapter: document.querySelector("#nextChapter"),
  themeToggle: document.querySelector("#themeToggle"),
  increaseFont: document.querySelector("#increaseFont"),
  decreaseFont: document.querySelector("#decreaseFont"),
  menuButton: document.querySelector("#menuButton"),
  library: document.querySelector("#library"),
  scrim: document.querySelector("#scrim"),
  chapterCount: document.querySelector("#chapterCount"),
  wordCount: document.querySelector("#wordCount")
};

const store = createStore();
let activeIndex = Number(store.get("reader:chapter") || 0);
let docs = [];
let sectionObserver;
const savedTheme = store.get("reader:theme");
const savedFont = Number(store.get("reader:font") || 19);

document.documentElement.dataset.theme = savedTheme || "";
document.documentElement.style.setProperty("--reader-size", `${savedFont}px`);

init();

async function init() {
  docs = await Promise.all(chapters.map(loadChapter));
  activeIndex = Math.min(Math.max(activeIndex, 0), docs.length - 1);
  els.chapterCount.textContent = `${docs.length} файлов`;
  els.wordCount.textContent = `~${Math.round(countWords(docs.map((doc) => doc.raw).join(" ")) / 1000)} тыс. слов`;
  renderChapterList(docs);
  openChapter(activeIndex, { restoreScroll: true });
  bindEvents();
}

async function loadChapter(chapter, index) {
  if (typeof chapter.raw === "string") {
    const raw = injectFigureImages(chapter.raw);
    const title = chapter.title || (raw.match(/^#\s+(.+)$/m) || [null, chapter.file])[1];
    const words = chapter.words || countWords(raw);
    return { ...chapter, index, raw, title, words };
  }

  const response = await fetch(`../translated/${chapter.file}`);
  if (!response.ok) {
    throw new Error(`Не удалось загрузить ${chapter.file}`);
  }
  const raw = injectFigureImages(await response.text());
  const title = (raw.match(/^#\s+(.+)$/m) || [null, chapter.file])[1];
  const words = countWords(raw);
  return { ...chapter, index, raw, title, words };
}

function bindEvents() {
  els.searchInput.addEventListener("input", () => renderChapterList(filterDocs(els.searchInput.value)));
  els.prevChapter.addEventListener("click", () => openChapter(activeIndex - 1));
  els.nextChapter.addEventListener("click", () => openChapter(activeIndex + 1));
  els.themeToggle.addEventListener("click", toggleTheme);
  els.increaseFont.addEventListener("click", () => adjustFont(1));
  els.decreaseFont.addEventListener("click", () => adjustFont(-1));
  els.menuButton.addEventListener("click", toggleLibrary);
  els.scrim.addEventListener("click", closeLibrary);
  window.addEventListener("scroll", updateProgress, { passive: true });
  window.addEventListener("beforeunload", saveReadingPosition);
}

function renderChapterList(items) {
  const query = els.searchInput.value.trim();
  els.chapterList.innerHTML = "";
  items.forEach((doc) => {
    const button = document.createElement("button");
    button.className = `chapter-card ${doc.index === activeIndex ? "active" : ""}`;
    button.type = "button";
    button.innerHTML = `
      <span class="chapter-index">${doc.label}</span>
      <span>
        <strong>${highlight(escapeHtml(doc.title), query)}</strong>
        <span>${doc.kind} · ${doc.words.toLocaleString("ru-RU")} слов</span>
      </span>
    `;
    button.addEventListener("click", () => {
      openChapter(doc.index);
      closeLibrary();
    });
    els.chapterList.appendChild(button);
  });
}

function openChapter(index, options = {}) {
  if (index < 0 || index >= docs.length) return;

  saveReadingPosition();
  activeIndex = index;
  const doc = docs[activeIndex];
  store.set("reader:chapter", String(activeIndex));
  els.currentKicker.textContent = doc.kind;
  els.currentTitle.textContent = doc.title;
  document.title = `${doc.title} | Читалка`;
  els.content.innerHTML = markdownToHtml(doc.raw);
  renderSections();
  renderChapterList(filterDocs(els.searchInput.value));
  els.prevChapter.disabled = activeIndex === 0;
  els.nextChapter.disabled = activeIndex === docs.length - 1;

  if (options.restoreScroll) {
    const y = Number(store.get(`reader:scroll:${doc.file}`) || 0);
    setTimeout(() => window.scrollTo({ top: y, behavior: "auto" }), 0);
  } else {
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
  setTimeout(updateProgress, 60);
}

function renderSections() {
  if (sectionObserver) sectionObserver.disconnect();
  const headings = [...els.content.querySelectorAll("h2, h3")];
  els.sectionRail.innerHTML = "";

  headings.forEach((heading, index) => {
    const id = `section-${activeIndex}-${index}`;
    heading.id = id;
    const link = document.createElement("a");
    link.href = `#${id}`;
    link.textContent = heading.textContent;
    els.sectionRail.appendChild(link);
  });

  sectionObserver = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      const link = els.sectionRail.querySelector(`[href="#${entry.target.id}"]`);
      els.sectionRail.querySelectorAll("a").forEach((item) => item.classList.remove("active"));
      if (link) link.classList.add("active");
    });
  }, { rootMargin: "-20% 0px -70% 0px" });

  headings.forEach((heading) => sectionObserver.observe(heading));
}

function injectFigureImages(markdown) {
  const existingFigures = new Set(
    [...markdown.matchAll(/!\[[^\]]*(?:Рис\.|Figure)\s*(\d+)/gi)].map((match) => match[1])
  );
  const insertedFigures = new Set();

  return markdown.replace(/^(\*\*Рис\.\s*(\d+)[^\n]*)$/gm, (match, line, figureNumber) => {
    const imageSrc = figureImageMap[figureNumber];
    if (!imageSrc || existingFigures.has(figureNumber) || insertedFigures.has(figureNumber)) {
      return match;
    }

    insertedFigures.add(figureNumber);
    return `![Рис. ${figureNumber}](${imageSrc})\n\n${line}`;
  });
}

function markdownToHtml(markdown) {
  const lines = markdown.replace(/\r\n/g, "\n").split("\n");
  const html = [];
  let list = null;
  let quote = [];

  const closeList = () => {
    if (!list) return;
    html.push(`</${list}>`);
    list = null;
  };
  const closeQuote = () => {
    if (!quote.length) return;
    html.push(`<blockquote>${quote.map((line) => `<p>${inline(line)}</p>`).join("")}</blockquote>`);
    quote = [];
  };

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    const trimmed = line.trim();
    if (!trimmed) {
      closeList();
      closeQuote();
      continue;
    }

    const heading = trimmed.match(/^(#{1,3})\s+(.+)$/);
    if (heading) {
      closeList();
      closeQuote();
      html.push(`<h${heading[1].length}>${inline(heading[2])}</h${heading[1].length}>`);
      continue;
    }

    const image = parseImageLine(trimmed);
    if (image) {
      closeList();
      closeQuote();
      const caption = findFollowingFigureCaption(lines, index);
      if (caption) {
        html.push(renderFigure(image.src, image.alt, caption.text));
        index = caption.index;
      } else {
        html.push(renderFigure(image.src, image.alt));
      }
      continue;
    }

    if (trimmed.startsWith(">")) {
      closeList();
      quote.push(trimmed.replace(/^>\s?/, ""));
      continue;
    }

    const unordered = trimmed.match(/^[-*]\s+(.+)$/);
    const ordered = trimmed.match(/^\d+\.\s+(.+)$/);
    if (unordered || ordered) {
      closeQuote();
      const type = unordered ? "ul" : "ol";
      if (list !== type) {
        closeList();
        html.push(`<${type}>`);
        list = type;
      }
      html.push(`<li>${inline((unordered || ordered)[1])}</li>`);
      continue;
    }

    closeList();
    closeQuote();
    html.push(`<p>${inline(trimmed)}</p>`);
  }

  closeList();
  closeQuote();
  return html.join("\n");
}

function parseImageLine(line) {
  const match = line.match(/^!\[([^\]]*)]\((?:<([^>]+)>|([^)]+))\)$/);
  if (!match) return null;
  return {
    alt: match[1],
    src: match[2] || match[3]
  };
}

function findFollowingFigureCaption(lines, imageLineIndex) {
  let index = imageLineIndex + 1;
  while (index < lines.length && !lines[index].trim()) {
    index += 1;
  }

  const line = lines[index]?.trim();
  if (!line || !/^\*\*Рис\.\s*\d+/.test(line)) return null;
  return {
    index,
    text: normalizeFigureCaption(line)
  };
}

function normalizeFigureCaption(line) {
  return line
    .replace(/^\*\*(Рис\.\s*\d+\.?)\*\*\s*/, "$1 ")
    .replace(/^\*\*/, "")
    .replace(/\*\*$/, "")
    .replace(/\s+/g, " ")
    .trim();
}

function renderFigure(src, alt, caption = "") {
  const fallbackAlt = caption || alt || "Иллюстрация";
  return `
    <figure class="book-figure">
      <div class="figure-frame">
        <img src="${escapeHtml(src)}" alt="${escapeHtml(fallbackAlt)}" loading="lazy">
      </div>
      ${caption ? `<figcaption>${inline(caption)}</figcaption>` : ""}
    </figure>
  `;
}

function inline(value) {
  const links = [];
  const createLink = (href, text = href) => {
    const token = `@@LINK_${links.length}@@`;
    links.push(`<a href="${href}" target="_blank" rel="noopener noreferrer">${text}</a>`);
    return token;
  };

  const linked = escapeHtml(value)
    .replace(/\[([^\]]+)]\((https?:\/\/[^)\s]+)\)/g, (_match, text, href) => createLink(href, text))
    .replace(/\bhttps?:\/\/[^\s<]+/g, (match) => {
      const punctuation = match.match(/[.,;:!?)]$/)?.[0] || "";
      const href = punctuation ? match.slice(0, -1) : match;
      return `${createLink(href)}${punctuation}`;
    });

  return linked
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\*([^*]+)\*/g, "<em>$1</em>")
    .replace(/@@LINK_(\d+)@@/g, (_match, index) => links[Number(index)]);
}

function filterDocs(query) {
  const clean = query.trim().toLowerCase();
  if (!clean) return docs;
  return docs.filter((doc) => `${doc.title}\n${doc.raw}`.toLowerCase().includes(clean));
}

function highlight(value, query) {
  const clean = query.trim();
  if (!clean) return value;
  const escaped = clean.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return value.replace(new RegExp(`(${escaped})`, "ig"), "<mark>$1</mark>");
}

function updateProgress() {
  const page = els.content;
  const rect = page.getBoundingClientRect();
  const total = page.offsetHeight - window.innerHeight * .5;
  const read = Math.min(Math.max(-rect.top, 0), Math.max(total, 1));
  els.readProgress.style.width = `${Math.round((read / Math.max(total, 1)) * 100)}%`;
}

function saveReadingPosition() {
  const doc = docs[activeIndex];
  if (!doc) return;
  store.set(`reader:scroll:${doc.file}`, String(Math.max(window.scrollY, 0)));
}

function toggleTheme() {
  const next = document.documentElement.dataset.theme === "night" ? "" : "night";
  document.documentElement.dataset.theme = next;
  store.set("reader:theme", next);
}

function adjustFont(delta) {
  const current = Number(getComputedStyle(document.documentElement).getPropertyValue("--reader-size").replace("px", ""));
  const next = Math.min(24, Math.max(16, current + delta));
  document.documentElement.style.setProperty("--reader-size", `${next}px`);
  store.set("reader:font", String(next));
}

function toggleLibrary() {
  els.library.classList.toggle("open");
  els.scrim.classList.toggle("open");
}

function closeLibrary() {
  els.library.classList.remove("open");
  els.scrim.classList.remove("open");
}

function countWords(value) {
  return (value.match(/[A-Za-zА-Яа-яЁё0-9-]+/g) || []).length;
}

function createDefaultFigureImageMap() {
  const map = {};
  for (let figure = 1; figure <= 36; figure += 1) {
    map[String(figure)] = `images/imageFile${figure + 1}.png`;
  }
  return map;
}

function createStore() {
  const memory = new Map();
  try {
    const testKey = "reader:test";
    window.localStorage.setItem(testKey, "1");
    window.localStorage.removeItem(testKey);
    return {
      get: (key) => window.localStorage.getItem(key),
      set: (key, value) => window.localStorage.setItem(key, value)
    };
  } catch (error) {
    return {
      get: (key) => memory.get(key) || null,
      set: (key, value) => memory.set(key, value)
    };
  }
}

function escapeHtml(value) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
