const docs = [
  {
    id: 'overview',
    title: 'Project overview',
    file: 'README.md',
    category: 'project'
  },
  {
    id: 'summary',
    title: 'Summary / market guide',
    file: 'summary.md',
    category: 'summary'
  },
  {
    id: 'touch-guides',
    title: '2-in-1 & touch laptops',
    file: '2in1_and_touch_laptops_guide.md',
    category: 'guide'
  },
  {
    id: 'elitebook-review',
    title: 'HP EliteBook x360 review',
    file: 'hp_elitebook_x360_830_g8_master_review.md',
    category: 'review'
  },
  {
    id: 'elitebook-accessories',
    title: 'EliteBook accessories guide',
    file: 'hp_elitebook_x360_accessories_guide.md',
    category: 'guide'
  }
];

const state = {
  activeDocId: 'overview',
  filter: 'all',
  query: ''
};

const tabList = document.getElementById('tabList');
const documentContent = document.getElementById('documentContent');
const searchInput = document.getElementById('searchInput');
const statusBar = document.getElementById('statusBar');

function normalizeText(value) {
  return String(value || '').toLowerCase();
}

function buildVisibleDocs() {
  return docs.filter((doc) => {
    const matchesFilter = state.filter === 'all' || doc.category === state.filter;
    const haystack = `${doc.title} ${doc.file}`.toLowerCase();
    const matchesQuery = !state.query || haystack.includes(state.query.toLowerCase());
    return matchesFilter && matchesQuery;
  });
}

function setStatus(message, type = 'info') {
  const badgeClass = type === 'error' ? 'status-badge error' : 'status-badge';
  statusBar.innerHTML = `<span class="${badgeClass}">${message}</span>`;
}

function getVisibleDoc() {
  const visibleDocs = buildVisibleDocs();
  const activeDoc = docs.find((doc) => doc.id === state.activeDocId);
  if (visibleDocs.length === 0) return null;
  if (activeDoc && visibleDocs.some((doc) => doc.id === activeDoc.id)) return activeDoc;
  return visibleDocs[0];
}

function renderTabs() {
  const visibleDocs = buildVisibleDocs();

  if (visibleDocs.length === 0) {
    tabList.innerHTML = '<div class="empty-state">No documents match your search or filter.</div>';
    return;
  }

  const selected = getVisibleDoc();
  if (selected) {
    state.activeDocId = selected.id;
  }

  tabList.innerHTML = visibleDocs
    .map(
      (doc) => `
        <button
          type="button"
          class="tab-button ${doc.id === state.activeDocId ? 'active' : ''}"
          data-doc-id="${doc.id}"
          role="tab"
          aria-selected="${doc.id === state.activeDocId}"
        >
          ${doc.title}
        </button>
      `
    )
    .join('');

  tabList.querySelectorAll('.tab-button').forEach((button) => {
    button.addEventListener('click', () => {
      state.activeDocId = button.dataset.docId;
      renderTabs();
      loadDocument();
    });
  });
}

function sanitizeMarkdown(rawText) {
  return rawText
    .replace(/!\[[^\]]*\]\((?:\/home\/[^)]+|\/[^)]+)\)/g, '')
    .replace(/\[(?:Current page|View Product)\]\(citation-section:[^)]+\)/g, '')
    .replace(/\[\s*\]\(https?:\/\/[^)]+\)/g, '');
}

async function loadDocument() {
  const selectedDoc = docs.find((doc) => doc.id === state.activeDocId) || buildVisibleDocs()[0];
  if (!selectedDoc) {
    documentContent.innerHTML = '<div class="empty-state">No matching document available.</div>';
    return;
  }

  setStatus(`Loading ${selectedDoc.title}…`);
  documentContent.innerHTML = '<div class="empty-state">Loading document…</div>';

  try {
    const response = await fetch(`./${selectedDoc.file}`, { cache: 'no-store' });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const markdown = await response.text();
    const sanitized = sanitizeMarkdown(markdown);
    const rendered = DOMPurify.sanitize(marked.parse(sanitized));
    documentContent.innerHTML = rendered;
    setStatus(`${selectedDoc.title} loaded`, 'success');
  } catch (error) {
    documentContent.innerHTML = `
      <div class="empty-state">
        <div>
          <h3>Unable to load this document.</h3>
          <p>${error.message}</p>
        </div>
      </div>
    `;
    setStatus('Could not load this document.', 'error');
  }
}

function updateFilterButtons() {
  document.querySelectorAll('.filter-btn').forEach((button) => {
    const isActive = button.dataset.filter === state.filter;
    button.classList.toggle('active', isActive);
  });
}

function bindEvents() {
  document.querySelectorAll('.filter-btn').forEach((button) => {
    button.addEventListener('click', () => {
      state.filter = button.dataset.filter;
      updateFilterButtons();
      renderTabs();
      loadDocument();
    });
  });

  searchInput.addEventListener('input', (event) => {
    state.query = event.target.value.trim();
    renderTabs();
    loadDocument();
  });
}

async function init() {
  bindEvents();
  renderTabs();
  await loadDocument();
}

init();
