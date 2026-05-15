"""Static frontend assets for the generated knowledge-base site."""

from __future__ import annotations


STYLES_CSS = r"""
:root {
  color-scheme: light;
  --bg: #f8faf9;
  --surface: #ffffff;
  --surface-soft: #f1f5f4;
  --ink: #172126;
  --text: #263238;
  --muted: #68757c;
  --faint: #8b969c;
  --line: #dbe3e1;
  --line-strong: #c6d1cf;
  --accent: #24786f;
  --accent-soft: #e3f1ee;
  --accent-strong: #155b55;
  --warning: #8a5a12;
  --warning-bg: #fff7e6;
  --code-bg: #152024;
  --shadow: 0 12px 36px rgba(19, 36, 42, 0.07);
  --radius: 8px;
  --page: min(1120px, calc(100vw - 40px));
  --reading: min(760px, calc(100vw - 40px));
  --font: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
    "Microsoft YaHei", "Noto Sans CJK SC", "Source Han Sans SC", sans-serif;
  --mono: "Cascadia Code", "SFMono-Regular", Consolas, "Liberation Mono", monospace;
}

* {
  box-sizing: border-box;
}

html {
  scroll-behavior: smooth;
}

body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: var(--font);
  line-height: 1.68;
  letter-spacing: 0;
}

a {
  color: inherit;
  text-decoration-color: color-mix(in srgb, var(--accent) 42%, transparent);
  text-decoration-thickness: 1px;
  text-underline-offset: 3px;
}

a:hover {
  color: var(--accent-strong);
  text-decoration-color: var(--accent-strong);
}

.site-shell {
  min-height: 100vh;
}

.site-header {
  width: var(--page);
  margin: 0 auto;
  min-height: 68px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  border-bottom: 1px solid var(--line);
}

.site-mark {
  font-weight: 800;
  color: var(--ink);
  text-decoration: none;
  letter-spacing: 0;
}

.site-nav {
  display: flex;
  align-items: center;
  gap: 4px;
}

.site-nav a {
  min-height: 36px;
  display: inline-flex;
  align-items: center;
  padding: 0 12px;
  border-radius: 999px;
  color: var(--muted);
  text-decoration: none;
  font-size: 0.94rem;
}

.site-nav a[aria-current="page"],
.site-nav a:hover {
  background: var(--surface-soft);
  color: var(--ink);
}

main {
  width: var(--page);
  margin: 0 auto;
}

.hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(260px, 340px);
  gap: 56px;
  align-items: end;
  padding: 76px 0 54px;
  border-bottom: 1px solid var(--line);
}

.hero-copy {
  max-width: 760px;
}

.eyebrow {
  display: block;
  color: var(--accent-strong);
  font-size: 0.78rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.hero h1,
.library-hero h1,
.reader h1 {
  margin: 12px 0 0;
  color: var(--ink);
  font-weight: 760;
  line-height: 1.08;
  letter-spacing: 0;
}

.hero h1 {
  max-width: 820px;
  font-size: clamp(2.4rem, 5.8vw, 4.9rem);
}

.hero p,
.library-hero p {
  max-width: 680px;
  margin: 22px 0 0;
  color: var(--muted);
  font-size: 1.08rem;
  line-height: 1.86;
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 30px;
}

.button {
  min-height: 42px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--accent);
  border-radius: 999px;
  background: var(--accent);
  color: #ffffff;
  padding: 0 18px;
  font-weight: 700;
  text-decoration: none;
}

.button:hover {
  background: var(--accent-strong);
  color: #ffffff;
}

.button.secondary {
  background: transparent;
  color: var(--accent-strong);
}

.summary-panel {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1px;
  margin: 0;
  border: 1px solid var(--line);
  background: var(--line);
}

.summary-panel div {
  min-height: 94px;
  background: var(--surface);
  padding: 16px;
}

.summary-panel dt {
  margin: 0;
  color: var(--muted);
  font-size: 0.78rem;
}

.summary-panel dd {
  margin: 8px 0 0;
  color: var(--ink);
  font-size: 1.55rem;
  font-weight: 760;
  line-height: 1.15;
  overflow-wrap: anywhere;
}

.page-section {
  padding: 42px 0;
  border-bottom: 1px solid var(--line);
}

.section-title {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 20px;
}

.section-title h2 {
  margin: 4px 0 0;
  color: var(--ink);
  font-size: 1.7rem;
  line-height: 1.2;
  letter-spacing: 0;
}

.section-title span,
.text-link {
  color: var(--muted);
  font-size: 0.92rem;
}

.feature-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(280px, 0.65fr);
  gap: 20px;
}

.feature-card,
.mini-card,
.article-card,
.latest-item {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
}

.feature-card {
  min-height: 330px;
  display: block;
  padding: clamp(24px, 4vw, 40px);
  text-decoration: none;
}

.feature-card h2 {
  max-width: 820px;
  margin: 16px 0 16px;
  color: var(--ink);
  font-size: clamp(1.8rem, 3.6vw, 3.55rem);
  line-height: 1.1;
  letter-spacing: 0;
}

.feature-card p {
  max-width: 780px;
  margin: 0;
  color: var(--muted);
  font-size: 1.03rem;
  line-height: 1.82;
}

.feature-side {
  display: grid;
  gap: 12px;
}

.mini-card {
  min-height: 112px;
  display: block;
  padding: 16px;
  text-decoration: none;
}

.mini-card h3,
.article-card h3,
.latest-item h3 {
  margin: 8px 0 0;
  color: var(--ink);
  font-size: 1.08rem;
  line-height: 1.38;
  letter-spacing: 0;
}

.feature-card:hover,
.mini-card:hover,
.article-card:hover,
.latest-item:hover {
  border-color: var(--line-strong);
  box-shadow: var(--shadow);
}

.meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  color: var(--muted);
  font-size: 0.8rem;
}

.score {
  min-width: 42px;
  min-height: 24px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid color-mix(in srgb, var(--accent) 35%, var(--line));
  border-radius: 999px;
  color: var(--accent-strong);
  background: var(--accent-soft);
  font-size: 0.76rem;
  font-weight: 800;
}

.source-pill,
.tag,
.quiet-link {
  min-height: 26px;
  display: inline-flex;
  align-items: center;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: var(--surface-soft);
  color: #3b4a4f;
  padding: 2px 9px;
  font-size: 0.78rem;
  text-decoration: none;
}

.tag {
  background: #ffffff;
}

.source-pill:hover,
.tag:hover,
.quiet-link:hover {
  border-color: color-mix(in srgb, var(--accent) 38%, var(--line));
  background: var(--accent-soft);
  color: var(--accent-strong);
}

.tag-row,
.source-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.topic-entry {
  display: grid;
  grid-template-columns: minmax(230px, 0.45fr) minmax(0, 1fr);
  gap: 28px;
  align-items: start;
}

.topic-entry h2 {
  margin: 6px 0 0;
  color: var(--ink);
  font-size: 1.35rem;
  line-height: 1.3;
}

.topic-groups {
  display: grid;
  gap: 12px;
}

.latest-list {
  display: grid;
  gap: 10px;
}

.latest-item {
  display: grid;
  grid-template-columns: minmax(170px, 0.34fr) minmax(220px, 0.44fr) minmax(0, 1fr);
  gap: 18px;
  align-items: start;
  padding: 16px 0;
  border-width: 0 0 1px;
  border-radius: 0;
  background: transparent;
}

.latest-item:last-child {
  border-bottom: 0;
}

.latest-item a {
  text-decoration: none;
}

.latest-item p {
  margin: 0;
  color: var(--muted);
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
  overflow: hidden;
}

.library-page {
  padding-bottom: 64px;
}

.library-hero {
  padding: 48px 0 30px;
}

.library-hero h1 {
  max-width: 760px;
  font-size: clamp(2rem, 4vw, 3.6rem);
}

.library-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  margin-top: 22px;
  color: var(--muted);
  font-size: 0.92rem;
}

.library-tools {
  position: sticky;
  top: 0;
  z-index: 2;
  display: grid;
  grid-template-columns: minmax(260px, 1.45fr) repeat(4, minmax(130px, 1fr));
  gap: 10px;
  margin: 6px 0 28px;
  padding: 14px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: color-mix(in srgb, var(--bg) 88%, white);
  backdrop-filter: blur(10px);
}

.library-tools label {
  display: grid;
  gap: 6px;
}

.library-tools span {
  color: var(--muted);
  font-size: 0.76rem;
  font-weight: 700;
}

.library-tools input,
.library-tools select {
  width: 100%;
  min-height: 40px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: var(--surface);
  color: var(--ink);
  padding: 0 11px;
  font: inherit;
}

.library-tools input:focus,
.library-tools select:focus {
  border-color: var(--accent);
  outline: 2px solid color-mix(in srgb, var(--accent) 18%, transparent);
}

.library-results {
  padding-top: 8px;
}

.article-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.article-card {
  min-height: 240px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 16px;
}

.article-card-main {
  color: inherit;
  text-decoration: none;
}

.article-card p {
  margin: 10px 0 0;
  color: var(--muted);
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 4;
  overflow: hidden;
}

.article-card .tag-row {
  margin-top: 16px;
}

.empty-state {
  display: none;
  border: 1px dashed var(--line-strong);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--muted);
  padding: 28px;
}

.article-topbar {
  width: var(--reading);
  margin: 0 auto;
  padding: 22px 0 0;
  display: flex;
  justify-content: space-between;
  gap: 16px;
  color: var(--muted);
  font-size: 0.92rem;
}

.reader {
  width: var(--reading);
  padding: 34px 0 72px;
}

.reader-header {
  border-bottom: 1px solid var(--line);
  padding-bottom: 28px;
}

.reader-kicker {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 18px;
}

.reader h1 {
  font-size: clamp(2rem, 5vw, 4.2rem);
}

.summary-lede {
  margin: 24px 0 0;
  padding-top: 20px;
  border-top: 1px solid var(--line);
  color: #334349;
  font-size: 1.13rem;
  line-height: 1.92;
}

.reader-meta {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1px;
  margin-top: 24px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--line);
  overflow: hidden;
}

.reader-meta div {
  background: var(--surface);
  padding: 12px;
}

.reader-meta span {
  display: block;
  color: var(--muted);
  font-size: 0.74rem;
  font-weight: 700;
}

.reader-meta strong {
  display: block;
  margin-top: 4px;
  color: var(--ink);
  font-size: 0.92rem;
  overflow-wrap: anywhere;
}

.content-state {
  margin-top: 24px;
  border: 1px solid color-mix(in srgb, var(--warning) 28%, var(--line));
  border-left: 3px solid var(--warning);
  border-radius: var(--radius);
  background: var(--warning-bg);
  color: #644615;
  padding: 14px 16px;
}

.toc {
  margin-top: 26px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--surface);
  padding: 14px 16px;
}

.toc summary {
  cursor: pointer;
  color: var(--ink);
  font-weight: 800;
}

.toc ol {
  margin: 12px 0 0;
  padding-left: 20px;
}

.prose {
  margin-top: 34px;
  color: #253238;
  font-size: 1.07rem;
  line-height: 1.92;
}

.prose h2,
.prose h3,
.prose h4 {
  color: var(--ink);
  line-height: 1.28;
  letter-spacing: 0;
  margin: 2.2em 0 0.7em;
}

.prose h2 {
  font-size: 1.85rem;
}

.prose h3 {
  font-size: 1.45rem;
}

.prose h4 {
  font-size: 1.2rem;
}

.prose p,
.prose ul,
.prose ol,
.prose blockquote,
.prose pre,
.prose table {
  margin: 1.1em 0;
}

.prose a {
  color: var(--accent-strong);
}

.prose blockquote {
  border-left: 3px solid var(--accent);
  margin-left: 0;
  padding-left: 18px;
  color: #42545a;
}

.prose code {
  border: 1px solid var(--line);
  border-radius: 5px;
  background: var(--surface-soft);
  padding: 0.12em 0.34em;
  font-family: var(--mono);
  font-size: 0.9em;
}

.prose pre {
  overflow-x: auto;
  border-radius: var(--radius);
  background: var(--code-bg);
  color: #eef7f2;
  padding: 16px;
}

.prose pre code {
  border: 0;
  background: transparent;
  color: inherit;
  padding: 0;
}

.prose table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.95rem;
}

.prose th,
.prose td {
  border: 1px solid var(--line);
  padding: 8px 10px;
  text-align: left;
  vertical-align: top;
}

.prose th {
  background: var(--surface-soft);
}

.related {
  margin-top: 46px;
  border-top: 1px solid var(--line);
  padding-top: 26px;
}

.related-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.article-nav {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-top: 30px;
  border-top: 1px solid var(--line);
  padding-top: 18px;
}

.article-nav a {
  max-width: 48%;
}

.site-footer {
  width: var(--page);
  margin: 0 auto;
  border-top: 1px solid var(--line);
  padding: 22px 0 28px;
  color: var(--faint);
  font-size: 0.84rem;
  text-align: center;
}

@media (max-width: 960px) {
  .hero,
  .feature-grid,
  .topic-entry {
    grid-template-columns: 1fr;
  }

  .library-tools {
    position: static;
    grid-template-columns: 1fr 1fr;
  }

  .library-tools .search-field {
    grid-column: 1 / -1;
  }

  .article-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .latest-item {
    grid-template-columns: minmax(130px, 0.34fr) minmax(0, 1fr);
  }

  .latest-item p {
    grid-column: 2;
  }
}

@media (max-width: 640px) {
  :root {
    --page: calc(100vw - 24px);
    --reading: calc(100vw - 24px);
  }

  .site-header {
    min-height: 60px;
  }

  .hero {
    padding: 48px 0 36px;
  }

  .summary-panel,
  .library-tools,
  .article-grid,
  .related-grid,
  .reader-meta {
    grid-template-columns: 1fr;
  }

  .feature-card,
  .mini-card,
  .article-card {
    padding: 16px;
  }

  .latest-item {
    grid-template-columns: 1fr;
    gap: 8px;
  }

  .latest-item p {
    grid-column: auto;
  }

  .section-title,
  .article-nav,
  .article-topbar {
    display: grid;
  }

  .article-nav a {
    max-width: none;
  }
}
"""


APP_JS = r"""
(function () {
  const articles = window.MYGK_SEARCH_DATA || [];
  const cards = Array.from(document.querySelectorAll("[data-article-card]"));
  const searchInput = document.querySelector("[data-search]");
  const tagFilter = document.querySelector("[data-tag-filter]");
  const sourceFilter = document.querySelector("[data-source-filter]");
  const scoreFilter = document.querySelector("[data-score-filter]");
  const sortSelect = document.querySelector("[data-sort]");
  const countLabel = document.querySelector("[data-count-label]");
  const emptyState = document.querySelector("[data-empty-state]");

  if (!cards.length) return;

  function setInitialFilters() {
    const params = new URLSearchParams(window.location.search);
    const controls = [
      [searchInput, params.get("q")],
      [tagFilter, params.get("tag")],
      [sourceFilter, params.get("source")],
      [scoreFilter, params.get("score")],
      [sortSelect, params.get("sort")]
    ];
    controls.forEach(([control, value]) => {
      if (!control || !value) return;
      const hasOption = control.tagName === "SELECT"
        ? Array.from(control.options).some((option) => option.value === value)
        : true;
      if (hasOption) control.value = value;
    });
  }

  function scorePass(score, mode) {
    if (!mode || mode === "all") return true;
    const value = Number(score || 0);
    if (mode === "high") return value >= 0.8;
    if (mode === "medium") return value >= 0.6 && value < 0.8;
    if (mode === "low") return value < 0.6;
    return true;
  }

  function matches(article) {
    const query = (searchInput && searchInput.value || "").trim().toLowerCase();
    const tag = tagFilter && tagFilter.value;
    const source = sourceFilter && sourceFilter.value;
    const scoreMode = scoreFilter && scoreFilter.value;
    const haystack = [
      article.title,
      article.summary,
      article.source,
      (article.tags || []).join(" ")
    ].join(" ").toLowerCase();
    return (!query || haystack.includes(query))
      && (!tag || tag === "all" || (article.tags || []).includes(tag))
      && (!source || source === "all" || article.source === source)
      && scorePass(article.relevance_score, scoreMode);
  }

  function compare(mode) {
    return function (a, b) {
      if (mode === "score") return Number(b.relevance_score || 0) - Number(a.relevance_score || 0);
      if (mode === "title") return String(a.title || "").localeCompare(String(b.title || ""));
      return String(b.organized_at || "").localeCompare(String(a.organized_at || ""));
    };
  }

  function syncUrl() {
    const params = new URLSearchParams();
    if (searchInput && searchInput.value.trim()) params.set("q", searchInput.value.trim());
    if (tagFilter && tagFilter.value !== "all") params.set("tag", tagFilter.value);
    if (sourceFilter && sourceFilter.value !== "all") params.set("source", sourceFilter.value);
    if (scoreFilter && scoreFilter.value !== "all") params.set("score", scoreFilter.value);
    if (sortSelect && sortSelect.value !== "latest") params.set("sort", sortSelect.value);
    const next = params.toString() ? `${window.location.pathname}?${params}` : window.location.pathname;
    window.history.replaceState(null, "", next);
  }

  function applyFilters() {
    const mode = sortSelect && sortSelect.value || "latest";
    const articleMap = new Map(articles.map((article) => [article.id, article]));
    const visible = articles.filter(matches).sort(compare(mode));
    const visibleIds = new Set(visible.map((article) => article.id));
    const cardMap = new Map(cards.map((card) => [card.getAttribute("data-article-card"), card]));
    const container = cards[0] && cards[0].parentNode;

    visible.forEach((article) => {
      const card = cardMap.get(article.id);
      if (card && container) container.appendChild(card);
    });

    cards.forEach((card) => {
      const article = articleMap.get(card.getAttribute("data-article-card"));
      card.hidden = !article || !visibleIds.has(article.id);
    });

    if (countLabel) countLabel.textContent = `${visible.length} 篇`;
    if (emptyState) emptyState.style.display = visible.length ? "none" : "block";
    syncUrl();
  }

  [searchInput, tagFilter, sourceFilter, scoreFilter, sortSelect].forEach((control) => {
    if (!control) return;
    control.addEventListener("input", applyFilters);
    control.addEventListener("change", applyFilters);
  });

  setInitialFilters();
  applyFilters();
})();
"""
