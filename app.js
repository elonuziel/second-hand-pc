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
  activePreset: 'all',
  catalogData: [],
  catalogFilters: {
    store: 'all',
    brand: 'all',
    ram: 0,
    form: 'all',
    screen: 'all',
    weight: 0,
    battery: 0,
    upgradability: 0,
    sort: 'value-desc'
  }
};

const tabList = typeof document !== 'undefined' ? document.getElementById('tabList') : null;
const documentContent = typeof document !== 'undefined' ? document.getElementById('documentContent') : null;
const catalogContent = typeof document !== 'undefined' ? document.getElementById('catalogContent') : null;
const searchInput = typeof document !== 'undefined' ? document.getElementById('searchInput') : null;
const statusBar = typeof document !== 'undefined' ? document.getElementById('statusBar') : null;

const documentSidebarCard = typeof document !== 'undefined' ? document.getElementById('documentSidebarCard') : null;
const catalogFiltersCard = typeof document !== 'undefined' ? document.getElementById('catalogFiltersCard') : null;
const catalogFilterFields = typeof document !== 'undefined' ? document.getElementById('catalogFilterFields') : null;
const toggleFiltersBtn = typeof document !== 'undefined' ? document.getElementById('toggleFiltersBtn') : null;
const resetFiltersBtn = typeof document !== 'undefined' ? document.getElementById('resetFiltersBtn') : null;
const themeToggle = typeof document !== 'undefined' ? document.getElementById('themeToggle') : null;

const storeFilter = typeof document !== 'undefined' ? document.getElementById('storeFilter') : null;
const brandFilter = typeof document !== 'undefined' ? document.getElementById('brandFilter') : null;
const ramFilter = typeof document !== 'undefined' ? document.getElementById('ramFilter') : null;
const formFilter = typeof document !== 'undefined' ? document.getElementById('formFilter') : null;
const screenFilter = typeof document !== 'undefined' ? document.getElementById('screenFilter') : null;
const weightFilter = typeof document !== 'undefined' ? document.getElementById('weightFilter') : null;
const batteryFilter = typeof document !== 'undefined' ? document.getElementById('batteryFilter') : null;
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

function calculateValueScore(laptop) {
  const price = laptop.deal_price_ils || laptop.price_ils || 0;
  if (price <= 300) return 5.0;

  const ramPts = (laptop.ram_gb || 8) * 12;
  const storagePts = (laptop.storage_gb || 256) * 0.1;
  const upgradePts = (laptop.upgradability_score || 5) * 12;

  let cpuBonus = 0;
  const cpuLower = (laptop.cpu || '').toLowerCase();
  if (cpuLower.includes('13th') || cpuLower.includes('14th') || cpuLower.includes('ultra')) cpuBonus = 80;
  else if (cpuLower.includes('12th') || cpuLower.includes('m2') || cpuLower.includes('m3')) cpuBonus = 65;
  else if (cpuLower.includes('11th') || cpuLower.includes('m1')) cpuBonus = 45;
  else if (cpuLower.includes('10th')) cpuBonus = 25;
  else if (cpuLower.includes('8th') || cpuLower.includes('9th')) cpuBonus = 10;

  // Battery capacity points (e.g. 50Wh -> 25 pts)
  const batteryPts = ((laptop.battery_wh || 50) - 30) * 1.5;

  // Weight penalty (lighter is better: 1.2kg bonus vs 2.5kg)
  const weightPts = Math.max(0, (2.5 - (laptop.weight_kg || 1.5)) * 25);

  const totalPoints = ramPts + storagePts + upgradePts + cpuBonus + batteryPts + weightPts;
  const rawRatio = (totalPoints / price) * 1000;
  const normalized = Math.min(9.9, Math.max(5.0, ((rawRatio - 80) / 190) * 4.9 + 5.0));
  return Number(normalized.toFixed(1));
}

function getBrandBadge(brand) {
  const b = (brand || '').toLowerCase();
  if (b.includes('lenovo')) return '<span class="brand-badge brand-lenovo">🔴 Lenovo</span>';
  if (b.includes('dell')) return '<span class="brand-badge brand-dell">🔵 Dell</span>';
  if (b.includes('hp')) return '<span class="brand-badge brand-hp">⚪ HP</span>';
  if (b.includes('apple')) return '<span class="brand-badge brand-apple">🍏 Apple</span>';
  if (b.includes('asus')) return '<span class="brand-badge brand-asus">⚡ Asus</span>';
  if (b.includes('microsoft')) return '<span class="brand-badge brand-ms">🪟 Microsoft</span>';
  return `<span class="brand-badge brand-default">💻 ${escapeHtml(brand || 'PC')}</span>`;
}

function getStoreClass(store) {
  const s = (store || '').toLowerCase();
  if (s.includes('outlet')) return 'store-itoutlet';
  if (s.includes('ecology') || s.includes('אקולוגיה')) return 'store-ecology';
  if (s.includes('lts') || s.includes('laptoptech') || s.includes('לפטופטק')) return 'store-lts';
  if (s.includes('recomp') || s.includes('ריקומפ')) return 'store-recomp';
  return 'store-default';
}

function setStatus(message, type = 'info') {
  const badgeClass = type === 'error' ? 'status-badge error' : 'status-badge';
  if (statusBar) {
    statusBar.innerHTML = `<span class="${badgeClass}">${escapeHtml(message)}</span>`;
  }
}

function initTheme() {
  if (typeof document === 'undefined') return;
  const savedTheme = localStorage.getItem('theme');
  const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  const theme = savedTheme || (prefersDark ? 'dark' : 'light');
  setTheme(theme);
}

function setTheme(theme) {
  if (typeof document === 'undefined') return;
  document.documentElement.setAttribute('data-theme', theme);
  try {
    localStorage.setItem('theme', theme);
  } catch (e) {}

  const themeIcon = document.getElementById('themeIcon');
  const themeText = document.querySelector('#themeToggle .theme-text');
  if (themeIcon) {
    themeIcon.textContent = theme === 'dark' ? '☀️' : '🌙';
  }
  if (themeText) {
    themeText.textContent = theme === 'dark' ? 'Light' : 'Dark';
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

    state.catalogData = unified.map((laptop, index) => {
      const brand = laptop.brand || 'Other';
      const store = laptop.store || 'Refurbished Store';
      const deal_price_ils = Number(laptop.deal_price_ils || laptop.price_ils) || 0;
      const price_ils = Number(laptop.price_ils || laptop.deal_price_ils) || 0;
      const ram_gb = Number(laptop.ram_gb) || 0;
      const storage_gb = Number(laptop.storage_gb) || 0;
      const upgradability_score = Number(laptop.upgradability_score) || 5.0;
      const cpu = laptop.cpu || 'N/A';

      const item = {
        id: `laptop-${index}-${store.replace(/\s+/g, '_')}`,
        title: laptop.title || laptop.model || 'Laptop Listing',
        brand,
        store,
        cpu,
        ram_gb,
        storage_gb,
        price_ils,
        deal_price_ils,
        deal_label: laptop.deal_label || `${deal_price_ils || price_ils || ''} ₪`,
        storage_type: laptop.storage_type || 'NVMe / SATA',
        ram_type: laptop.ram_type || 'Standard',
        upgradability_score,
        warranty_months: laptop.warranty_months || 12,
        is_touch: Boolean(laptop.is_touch),
        is_2in1: Boolean(laptop.is_2in1),
        url: laptop.url || '#',
        screen_size_in: Number(laptop.screen_size_in) || 14.0,
        weight_kg: Number(laptop.weight_kg) || 1.5,
        battery_wh: Number(laptop.battery_wh) || 50
      };
      item.value_score = calculateValueScore(item);
      return item;
    });
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

function setQuickPreset(preset) {
  state.activePreset = preset;

  if (preset === 'top-value') {
    state.catalogFilters.sort = 'value-desc';
    if (sortFilter) sortFilter.value = 'value-desc';
  } else if (preset === 'ram-32') {
    state.catalogFilters.ram = 32;
    if (ramFilter) ramFilter.value = '32';
  } else if (preset === '2in1') {
    state.catalogFilters.form = '2in1';
    if (formFilter) formFilter.value = '2in1';
  } else if (preset === 'modular') {
    state.catalogFilters.upgradability = 7;
    if (upgradabilityFilter) upgradabilityFilter.value = '7';
  } else if (preset === 'budget') {
    state.catalogFilters.sort = 'price-asc';
    if (sortFilter) sortFilter.value = 'price-asc';
  } else if (preset === 'featherlight') {
    state.catalogFilters.weight = 1.3;
    if (weightFilter) weightFilter.value = '1.3';
  } else if (preset === 'large-screen') {
    state.catalogFilters.screen = 'large';
    if (screenFilter) screenFilter.value = 'large';
  } else if (preset === 'long-battery') {
    state.catalogFilters.battery = 55;
    if (batteryFilter) batteryFilter.value = '55';
  } else if (preset === 'all') {
    state.catalogFilters = {
      store: 'all',
      brand: 'all',
      ram: 0,
      form: 'all',
      screen: 'all',
      weight: 0,
      battery: 0,
      upgradability: 0,
      sort: 'value-desc'
    };
    if (storeFilter) storeFilter.value = 'all';
    if (brandFilter) brandFilter.value = 'all';
    if (ramFilter) ramFilter.value = '0';
    if (formFilter) formFilter.value = 'all';
    if (screenFilter) screenFilter.value = 'all';
    if (weightFilter) weightFilter.value = '0';
    if (batteryFilter) batteryFilter.value = '0';
    if (upgradabilityFilter) upgradabilityFilter.value = '0';
    if (sortFilter) sortFilter.value = 'value-desc';
  }

  renderCatalog();
}

function renderCatalog() {
  if (!catalogContent) return;
  const { store, brand, ram, form, screen, weight, battery, upgradability, sort } = state.catalogFilters;
  const q = state.query.toLowerCase();

  let filtered = state.catalogData.filter((item) => {
    if (store !== 'all' && item.store !== store) return false;
    if (brand !== 'all' && item.brand.toLowerCase() !== brand.toLowerCase()) return false;
    if (ram > 0 && item.ram_gb < ram) return false;
    if (upgradability > 0 && item.upgradability_score < upgradability) return false;

    if (form === '2in1' && (!item.is_2in1 && !item.is_touch)) return false;
    if (form === 'clamshell' && (item.is_2in1 || item.is_touch)) return false;

    if (screen === 'compact' && item.screen_size_in > 13.5) return false;
    if (screen === '14.0' && Math.abs(item.screen_size_in - 14.0) > 0.3) return false;
    if (screen === 'large' && item.screen_size_in < 15.0) return false;

    if (weight > 0 && item.weight_kg > weight) return false;
    if (battery > 0 && item.battery_wh < battery) return false;

    if (q) {
      const searchHaystack = `${item.title} ${item.brand} ${item.store} ${item.cpu} ${item.ram_gb}GB ${item.storage_gb}GB ${item.screen_size_in}inch ${item.weight_kg}kg ${item.battery_wh}wh ${item.storage_type}`.toLowerCase();
      if (!searchHaystack.includes(q)) return false;
    }

    return true;
  });

  // Sorting
  filtered.sort((a, b) => {
    if (sort === 'value-desc') return (b.value_score || 0) - (a.value_score || 0);
    if (sort === 'price-asc') return a.deal_price_ils - b.deal_price_ils;
    if (sort === 'price-desc') return b.deal_price_ils - a.deal_price_ils;
    if (sort === 'weight-asc') return a.weight_kg - b.weight_kg;
    if (sort === 'battery-desc') return b.battery_wh - a.battery_wh;
    if (sort === 'screen-desc') return b.screen_size_in - a.screen_size_in;
    if (sort === 'upgrade-desc') return b.upgradability_score - a.upgradability_score;
    if (sort === 'ram-desc') return b.ram_gb - a.ram_gb;
    return 0;
  });

  // Identify top 3 value picks in current filtered view
  const topValueIds = new Set(
    [...filtered]
      .filter((l) => (l.deal_price_ils || l.price_ils) > 0 && l.value_score > 0)
      .sort((a, b) => b.value_score - a.value_score)
      .slice(0, 3)
      .map((l) => l.id)
  );

  setStatus(`Catalog: Found ${filtered.length} laptops matching criteria`, 'success');

  const chipsHtml = `
    <div class="quick-chips-container">
      <div class="quick-chips-header">⚡ Quick Explore Filters</div>
      <div class="quick-filter-chips">
        <button type="button" class="chip-btn ${state.activePreset === 'all' ? 'active' : ''}" data-preset="all">✨ All Laptops</button>
        <button type="button" class="chip-btn ${state.activePreset === 'top-value' ? 'active' : ''}" data-preset="top-value">🏆 Top Value Picks</button>
        <button type="button" class="chip-btn ${state.activePreset === 'featherlight' ? 'active' : ''}" data-preset="featherlight">🪶 Featherlight (&lt; 1.3kg)</button>
        <button type="button" class="chip-btn ${state.activePreset === 'long-battery' ? 'active' : ''}" data-preset="long-battery">🔋 Long Battery (55Wh+)</button>
        <button type="button" class="chip-btn ${state.activePreset === 'large-screen' ? 'active' : ''}" data-preset="large-screen">🖥️ Large Display (15"+)</button>
        <button type="button" class="chip-btn ${state.activePreset === 'ram-32' ? 'active' : ''}" data-preset="ram-32">⚡ 32GB RAM Deals</button>
        <button type="button" class="chip-btn ${state.activePreset === '2in1' ? 'active' : ''}" data-preset="2in1">🔄 2-in-1 / Touch</button>
        <button type="button" class="chip-btn ${state.activePreset === 'modular' ? 'active' : ''}" data-preset="modular">🟢 Modular (7+)</button>
        <button type="button" class="chip-btn ${state.activePreset === 'budget' ? 'active' : ''}" data-preset="budget">💰 Budget Deals</button>
      </div>
    </div>
  `;

  if (filtered.length === 0) {
    catalogContent.innerHTML = `
      ${chipsHtml}
      <div class="empty-state">
        <h3>No laptops match your current filter and search settings.</h3>
        <p>Try resetting or relaxing your filter options.</p>
      </div>
    `;
    bindChipButtons();
    return;
  }

  const cardsHtml = filtered
    .map((laptop) => {
      const isTopValue = topValueIds.has(laptop.id);
      return `
        <div class="catalog-card ${isTopValue ? 'top-value-card' : ''}">
          <div class="card-header">
            <div class="card-title-group">
              <div class="tags-row">
                ${getBrandBadge(laptop.brand)}
                <span class="store-tag ${getStoreClass(laptop.store)}">${escapeHtml(laptop.store)}</span>
                ${isTopValue ? '<span class="value-pick-badge">🏆 Best Value Pick</span>' : ''}
              </div>
              <h3 class="laptop-title">${escapeHtml(laptop.title)}</h3>
            </div>
            <div class="price-box">
              <span class="price-value">${laptop.deal_price_ils ? escapeHtml(laptop.deal_price_ils.toLocaleString()) + ' ₪' : 'Check Store'}</span>
              ${laptop.deal_label && !laptop.deal_label.includes(laptop.deal_price_ils) ? `<span class="deal-note">${escapeHtml(laptop.deal_label)}</span>` : ''}
              <span class="value-score-badge" title="Algorithm score based on CPU gen, RAM, SSD and Price">⭐ ${laptop.value_score}/10 Value</span>
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
              <span class="spec-label">Screen & Weight:</span>
              <span class="spec-value">${laptop.screen_size_in}" | ⚖️ ${laptop.weight_kg} kg</span>
            </div>
            <div class="spec-item">
              <span class="spec-label">Battery Capacity:</span>
              <span class="spec-value">🔋 ${laptop.battery_wh} Wh</span>
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
      `;
    })
    .join('');

  catalogContent.innerHTML = `
    ${chipsHtml}
    <div class="catalog-summary-bar">
      <span>Showing <strong>${filtered.length}</strong> available laptops</span>
    </div>
    <div class="catalog-grid">${cardsHtml}</div>
  `;

  bindChipButtons();
}

function bindChipButtons() {
  if (typeof document === 'undefined') return;
  document.querySelectorAll('.chip-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      setQuickPreset(btn.dataset.preset);
    });
  });
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

  if (themeToggle) {
    themeToggle.addEventListener('click', () => {
      const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
      const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
      setTheme(newTheme);
    });
  }

  if (toggleFiltersBtn && catalogFilterFields) {
    toggleFiltersBtn.addEventListener('click', () => {
      const isHidden = catalogFilterFields.classList.toggle('collapsed');
      toggleFiltersBtn.setAttribute('aria-expanded', !isHidden);
      const arrowSpan = toggleFiltersBtn.querySelector('.toggle-arrow');
      if (arrowSpan) {
        arrowSpan.textContent = isHidden ? '▾' : '▴';
      }
    });
  }

  if (resetFiltersBtn) {
    resetFiltersBtn.addEventListener('click', () => {
      setQuickPreset('all');
    });
  }

  if (storeFilter) {
    storeFilter.addEventListener('change', (e) => {
      state.catalogFilters.store = e.target.value;
      state.activePreset = '';
      renderCatalog();
    });
  }

  if (brandFilter) {
    brandFilter.addEventListener('change', (e) => {
      state.catalogFilters.brand = e.target.value;
      state.activePreset = '';
      renderCatalog();
    });
  }

  if (ramFilter) {
    ramFilter.addEventListener('change', (e) => {
      state.catalogFilters.ram = Number(e.target.value);
      state.activePreset = '';
      renderCatalog();
    });
  }

  if (formFilter) {
    formFilter.addEventListener('change', (e) => {
      state.catalogFilters.form = e.target.value;
      state.activePreset = '';
      renderCatalog();
    });
  }

  if (screenFilter) {
    screenFilter.addEventListener('change', (e) => {
      state.catalogFilters.screen = e.target.value;
      state.activePreset = '';
      renderCatalog();
    });
  }

  if (weightFilter) {
    weightFilter.addEventListener('change', (e) => {
      state.catalogFilters.weight = Number(e.target.value);
      state.activePreset = '';
      renderCatalog();
    });
  }

  if (batteryFilter) {
    batteryFilter.addEventListener('change', (e) => {
      state.catalogFilters.battery = Number(e.target.value);
      state.activePreset = '';
      renderCatalog();
    });
  }

  if (upgradabilityFilter) {
    upgradabilityFilter.addEventListener('change', (e) => {
      state.catalogFilters.upgradability = Number(e.target.value);
      state.activePreset = '';
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
  initTheme();
  bindEvents();
  await Promise.all([preloadDocContents(), loadCatalogData()]);
  updateViewMode();
}

init();

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { escapeHtml, calculateValueScore };
}
