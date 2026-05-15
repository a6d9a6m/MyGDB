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
