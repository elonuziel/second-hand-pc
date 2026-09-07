const docs = [
  {
    id: 'overview',
    title: 'Project Overview',
    file: 'README.md',
    category: 'project',
    content: ''
  },
  {
    id: 'summary',
    title: 'Summary / Market Guide',
    file: 'summary.md',
    category: 'summary',
    content: ''
  },
  {
    id: 'touch-guides',
    title: '2-in-1 & Touch Laptops Guide',
    file: '2in1_and_touch_laptops_guide.md',
    category: 'guide',
    content: ''
  },
  {
    id: 'elitebook-review',
    title: 'HP EliteBook x360 Review',
    file: 'hp_elitebook_x360_830_g8_master_review.md',
    category: 'review',
    content: ''
  },
  {
    id: 'elitebook-accessories',
    title: 'EliteBook Accessories Guide',
    file: 'hp_elitebook_x360_accessories_guide.md',
    category: 'guide',
    content: ''
  }
];

const state = {
  activeDocId: 'overview',
  filter: 'all', // 'all', 'project', 'summary', 'guide', 'review', 'catalog'
  query: '',
  catalogData: [],
  catalogFilters: {
    store: 'all',
    brand: 'all',
    ram: 0,
    form: 'all',
    upgradability: 0,
    sort: 'price-asc'
  }
};

const tabList = typeof document !== 'undefined' ? document.getElementById('tabList') : null;
const documentContent = typeof document !== 'undefined' ? document.getElementById('documentContent') : null;
const catalogContent = typeof document !== 'undefined' ? document.getElementById('catalogContent') : null;
const searchInput = typeof document !== 'undefined' ? document.getElementById('searchInput') : null;
const statusBar = typeof document !== 'undefined' ? document.getElementById('statusBar') : null;

const documentSidebarCard = typeof document !== 'undefined' ? document.getElementById('documentSidebarCard') : null;
const catalogFiltersCard = typeof document !== 'undefined' ? document.getElementById('catalogFiltersCard') : null;

const storeFilter = typeof document !== 'undefined' ? document.getElementById('storeFilter') : null;
const brandFilter = typeof document !== 'undefined' ? document.getElementById('brandFilter') : null;
const ramFilter = typeof document !== 'undefined' ? document.getElementById('ramFilter') : null;
const formFilter = typeof document !== 'undefined' ? document.getElementById('formFilter') : null;
const upgradabilityFilter = typeof document !== 'undefined' ? document.getElementById('upgradabilityFilter') : null;
const sortFilter = typeof document !== 'undefined' ? document.getElementById('sortFilter') : null;

function escapeHtml(str) {
  return String(str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function setStatus(message, type = 'info') {
  const badgeClass = type === 'error' ? 'status-badge error' : 'status-badge';
  if (statusBar) {
    statusBar.innerHTML = `<span class="${badgeClass}">${escapeHtml(message)}</span>`;
  }
}

async function preloadDocContents() {
  await Promise.all(
    docs.map(async (doc) => {
      try {
        const res = await fetch(`./${doc.file}`, { cache: 'no-store' });
        if (res.ok) {
          doc.content = await res.text();
        }
      } catch (e) {
        console.warn(`Could not preload ${doc.file}`, e);
      }
    })
  );
}

async function loadCatalogData() {
  try {
    const res = await fetch('./scraped_laptops.json', { cache: 'no-store' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const rawJson = await res.json();

    let unified = [];
    if (Array.isArray(rawJson)) {
      unified = rawJson;
    } else if (typeof rawJson === 'object') {
      Object.keys(rawJson).forEach((key) => {
        if (Array.isArray(rawJson[key])) {
          unified = unified.concat(rawJson[key]);
        }
      });
    }

    state.catalogData = unified.map((laptop) => ({
      title: laptop.title || laptop.model || 'Laptop Listing',
      brand: laptop.brand || 'Other',
      store: laptop.store || 'Refurbished Store',
      cpu: laptop.cpu || 'N/A',
      ram_gb: Number(laptop.ram_gb) || 0,
      storage_gb: Number(laptop.storage_gb) || 0,
      price_ils: Number(laptop.price_ils || laptop.deal_price_ils) || 0,
      deal_price_ils: Number(laptop.deal_price_ils || laptop.price_ils) || 0,
      deal_label: laptop.deal_label || `${laptop.deal_price_ils || laptop.price_ils || ''} ₪`,
      storage_type: laptop.storage_type || 'NVMe / SATA',
      ram_type: laptop.ram_type || 'Standard',
      upgradability_score: Number(laptop.upgradability_score) || 5.0,
      warranty_months: laptop.warranty_months || 12,
      is_touch: Boolean(laptop.is_touch),
      is_2in1: Boolean(laptop.is_2in1),
      url: laptop.url || '#'
    }));
  } catch (err) {
    console.warn('Failed to load scraped_laptops.json', err);
    state.catalogData = [];
  }
}

function buildVisibleDocs() {
  return docs.filter((doc) => {
    const matchesFilter = state.filter === 'all' || doc.category === state.filter;
    const searchTarget = `${doc.title} ${doc.file} ${doc.content || ''}`.toLowerCase();
    const matchesQuery = !state.query || searchTarget.includes(state.query.toLowerCase());
    return matchesFilter && matchesQuery;
  });
}

function getVisibleDoc() {
  const visibleDocs = buildVisibleDocs();
  const activeDoc = docs.find((doc) => doc.id === state.activeDocId);
  if (visibleDocs.length === 0) return null;
  if (activeDoc && visibleDocs.some((doc) => doc.id === activeDoc.id)) return activeDoc;
  return visibleDocs[0];
}

function renderTabs() {
  if (!tabList) return;
  const visibleDocs = buildVisibleDocs();

  if (visibleDocs.length === 0) {
    tabList.innerHTML = '<div class="empty-state">No matching documents found.</div>';
    return;
  }

  const selected = getVisibleDoc();
  if (selected) {
    state.activeDocId = selected.id;
  }

  tabList.innerHTML = visibleDocs
    .map((doc) => {
      const q = state.query ? state.query.toLowerCase() : '';
      const contentMatches = q && doc.content && doc.content.toLowerCase().includes(q) && !doc.title.toLowerCase().includes(q);
      const badgeHtml = contentMatches ? '<span class="match-badge">Text match</span>' : '';

      return `
        <button
          type="button"
          class="tab-button ${doc.id === state.activeDocId ? 'active' : ''}"
          data-doc-id="${escapeHtml(doc.id)}"
          role="tab"
          aria-selected="${doc.id === state.activeDocId}"
        >
          <span>${escapeHtml(doc.title)}</span>
          ${badgeHtml}
        </button>
      `;
    })
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
  if (state.filter === 'catalog') return;
  if (!documentContent) return;

  const selectedDoc = docs.find((doc) => doc.id === state.activeDocId) || buildVisibleDocs()[0];
  if (!selectedDoc) {
    documentContent.innerHTML = '<div class="empty-state">No matching document available.</div>';
    return;
  }

  setStatus(`Loading ${selectedDoc.title}…`);
  documentContent.innerHTML = '<div class="empty-state">Loading document…</div>';

  try {
    let markdown = selectedDoc.content;
    if (!markdown) {
      const response = await fetch(`./${selectedDoc.file}`, { cache: 'no-store' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      markdown = await response.text();
      selectedDoc.content = markdown;
    }

    const sanitized = sanitizeMarkdown(markdown);
    const rendered = DOMPurify.sanitize(marked.parse(sanitized));
    documentContent.innerHTML = rendered;
    setStatus(`${selectedDoc.title} loaded`, 'success');
  } catch (error) {
    documentContent.innerHTML = `
      <div class="empty-state">
        <div>
          <h3>Unable to load this document.</h3>
          <p>${escapeHtml(error.message)}</p>
        </div>
      </div>
    `;
    setStatus('Could not load this document.', 'error');
  }
}

function getUpgradabilityBadge(score) {
  if (score >= 8.5) return `<span class="score-badge score-high">🟢 ${score}/10</span>`;
  if (score >= 6.5) return `<span class="score-badge score-mid">🟡 ${score}/10</span>`;
  if (score >= 4.0) return `<span class="score-badge score-low">🟠 ${score}/10</span>`;
  return `<span class="score-badge score-locked">🔴 ${score}/10</span>`;
}

function renderCatalog() {
  if (!catalogContent) return;
  const { store, brand, ram, form, upgradability, sort } = state.catalogFilters;
  const q = state.query.toLowerCase();

  let filtered = state.catalogData.filter((item) => {
    if (store !== 'all' && item.store !== store) return false;
    if (brand !== 'all' && item.brand.toLowerCase() !== brand.toLowerCase()) return false;
    if (ram > 0 && item.ram_gb < ram) return false;
    if (upgradability > 0 && item.upgradability_score < upgradability) return false;

    if (form === '2in1' && (!item.is_2in1 && !item.is_touch)) return false;
    if (form === 'clamshell' && (item.is_2in1 || item.is_touch)) return false;

    if (q) {
      const searchHaystack = `${item.title} ${item.brand} ${item.store} ${item.cpu} ${item.ram_gb}GB ${item.storage_gb}GB ${item.storage_type}`.toLowerCase();
      if (!searchHaystack.includes(q)) return false;
    }

    return true;
  });

  // Sorting
  filtered.sort((a, b) => {
    if (sort === 'price-asc') return a.deal_price_ils - b.deal_price_ils;
    if (sort === 'price-desc') return b.deal_price_ils - a.deal_price_ils;
    if (sort === 'upgrade-desc') return b.upgradability_score - a.upgradability_score;
    if (sort === 'ram-desc') return b.ram_gb - a.ram_gb;
    return 0;
  });

  setStatus(`Catalog: Found ${filtered.length} laptops matching criteria`, 'success');

  if (filtered.length === 0) {
    catalogContent.innerHTML = `
      <div class="empty-state">
        <h3>No laptops match your current filter and search settings.</h3>
        <p>Try resetting or relaxing your filter options.</p>
      </div>
    `;
    return;
  }

  const cardsHtml = filtered
    .map(
      (laptop) => `
      <div class="catalog-card">
        <div class="card-header">
          <div class="card-title-group">
            <span class="store-tag">${escapeHtml(laptop.store)}</span>
            <h3 class="laptop-title">${escapeHtml(laptop.title)}</h3>
          </div>
          <div class="price-box">
            <span class="price-value">${laptop.deal_price_ils ? escapeHtml(laptop.deal_price_ils.toLocaleString()) + ' ₪' : 'Check Store'}</span>
            ${laptop.deal_label && !laptop.deal_label.includes(laptop.deal_price_ils) ? `<span class="deal-note">${escapeHtml(laptop.deal_label)}</span>` : ''}
          </div>
        </div>

        <div class="specs-grid">
          <div class="spec-item">
            <span class="spec-label">CPU:</span>
            <span class="spec-value">${escapeHtml(laptop.cpu)}</span>
          </div>
          <div class="spec-item">
            <span class="spec-label">RAM:</span>
            <span class="spec-value">${escapeHtml(laptop.ram_gb)} GB (${escapeHtml(laptop.ram_type)})</span>
          </div>
          <div class="spec-item">
            <span class="spec-label">Storage:</span>
            <span class="spec-value">${escapeHtml(laptop.storage_gb)} GB (${escapeHtml(laptop.storage_type)})</span>
          </div>
          <div class="spec-item">
            <span class="spec-label">Upgradability:</span>
            <span class="spec-value">${getUpgradabilityBadge(laptop.upgradability_score)}</span>
          </div>
          <div class="spec-item">
            <span class="spec-label">Form Factor:</span>
            <span class="spec-value">${laptop.is_2in1 ? '🔄 2-in-1 Convertible' : laptop.is_touch ? '💻 Touchscreen Clamshell' : '💻 Standard Clamshell'}</span>
          </div>
          <div class="spec-item">
            <span class="spec-label">Warranty:</span>
            <span class="spec-value">${escapeHtml(laptop.warranty_months)} Months Warranty</span>
          </div>
        </div>

        <div class="card-footer">
          <a href="${escapeHtml(laptop.url)}" target="_blank" rel="noopener noreferrer" class="buy-btn">
            View on Store ↗
          </a>
        </div>
      </div>
    `
    )
    .join('');

  catalogContent.innerHTML = `
    <div class="catalog-summary-bar">
      <span>Showing <strong>${filtered.length}</strong> available laptops</span>
    </div>
    <div class="catalog-grid">${cardsHtml}</div>
  `;
}

function updateViewMode() {
  if (state.filter === 'catalog') {
    if (documentSidebarCard) documentSidebarCard.classList.add('hidden');
    if (catalogFiltersCard) catalogFiltersCard.classList.remove('hidden');
    if (documentContent) documentContent.classList.add('hidden');
    if (catalogContent) catalogContent.classList.remove('hidden');
    renderCatalog();
  } else {
    if (documentSidebarCard) documentSidebarCard.classList.remove('hidden');
    if (catalogFiltersCard) catalogFiltersCard.classList.add('hidden');
    if (documentContent) documentContent.classList.remove('hidden');
    if (catalogContent) catalogContent.classList.add('hidden');
    renderTabs();
    loadDocument();
  }
}

function updateFilterButtons() {
  if (typeof document === 'undefined') return;
  document.querySelectorAll('.filter-btn').forEach((button) => {
    const isActive = button.dataset.filter === state.filter;
    button.classList.toggle('active', isActive);
  });
}

function bindEvents() {
  if (typeof document === 'undefined') return;

  document.querySelectorAll('.filter-btn').forEach((button) => {
    button.addEventListener('click', () => {
      state.filter = button.dataset.filter;
      updateFilterButtons();
      updateViewMode();
    });
  });

  if (searchInput) {
    searchInput.addEventListener('input', (event) => {
      state.query = event.target.value.trim();
      if (state.filter === 'catalog') {
        renderCatalog();
      } else {
        renderTabs();
        loadDocument();
      }
    });
  }

  if (storeFilter) {
    storeFilter.addEventListener('change', (e) => {
      state.catalogFilters.store = e.target.value;
      renderCatalog();
    });
  }

  if (brandFilter) {
    brandFilter.addEventListener('change', (e) => {
      state.catalogFilters.brand = e.target.value;
      renderCatalog();
    });
  }

  if (ramFilter) {
    ramFilter.addEventListener('change', (e) => {
      state.catalogFilters.ram = Number(e.target.value);
      renderCatalog();
    });
  }

  if (formFilter) {
    formFilter.addEventListener('change', (e) => {
      state.catalogFilters.form = e.target.value;
      renderCatalog();
    });
  }

  if (upgradabilityFilter) {
    upgradabilityFilter.addEventListener('change', (e) => {
      state.catalogFilters.upgradability = Number(e.target.value);
      renderCatalog();
    });
  }

  if (sortFilter) {
    sortFilter.addEventListener('change', (e) => {
      state.catalogFilters.sort = e.target.value;
      renderCatalog();
    });
  }
}

async function init() {
  if (typeof document === 'undefined') return;
  bindEvents();
  await Promise.all([preloadDocContents(), loadCatalogData()]);
  updateViewMode();
}

init();

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { escapeHtml };
}
