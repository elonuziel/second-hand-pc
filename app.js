/* ==========================================================================
   Second-Hand PC Hub — Refurbished Laptop & Mobile Catalog Application
   ========================================================================== */

/* --------------------------------------------------------------------------
   1. STATE MANAGEMENT & CONFIGURATION
   -------------------------------------------------------------------------- */

const docs = [
  {
    id: 'summary',
    title: 'Market Research Guide',
    file: 'data/full_catalog.md',
    category: 'summary',
    content: ''
  }
];

const state = {
  activeDocId: 'summary',
  filter: 'catalog', // 'catalog' or 'guide'
  query: '',
  activePreset: 'all',
  viewMode: 'grid', // 'grid' or 'table'
  catalogData: [],
  comparedIds: new Set(),
  catalogFilters: {
    category: 'all', // 'all' (laptops) or 'phones'
    store: 'all',
    brands: [], // Selected brands array
    priceMax: 5000,
    ramMin: 0,
    storageMin: 0,
    cpuGenMin: 0,
    swappableRamOnly: false,
    ultralightOnly: false,
    hideStale: false,
    sort: 'value-desc'
  }
};

const PAGE_SIZE = 24;
let currentFilteredItems = [];
let currentTopValueIds = new Set();
let renderedCount = 0;
let catalogObserver = null;
let mobileDataPromise = null;
let rafPending = false;

/* --------------------------------------------------------------------------
   2. DOM ELEMENTS CACHE
   -------------------------------------------------------------------------- */

const $ = (id) => (typeof document !== 'undefined' ? document.getElementById(id) : null);

const catalogContent = $('catalogContent');
const documentContent = $('documentContent');
const resultsCount = $('resultsCount');
const activePresetBadge = $('activePresetBadge');

const searchInput = $('searchInput');
const mobileSearchInput = $('mobileSearchInput');
const themeToggle = $('themeToggle');
const viewToggleGrid = $('viewToggleGrid');
const viewToggleTable = $('viewToggleTable');
const viewToggleGuide = $('viewToggleGuide');
const exportCsvBtn = $('exportCsvBtn');

const categoryChips = $('categoryChips');
const storeSelect = $('storeSelect');
const priceSlider = $('priceSlider');
const priceOutput = $('priceOutput');
const priceMinLabel = $('priceMinLabel');
const priceMaxLabel = $('priceMaxLabel');
const brandPills = $('brandPills');
const ramPills = $('ramPills');
const storagePills = $('storagePills');
const cpuGenGroup = $('cpuGenGroup');
const cpuGenSelect = $('cpuGenSelect');
const swappableRamToggle = $('swappableRamToggle');
const ultralightToggle = $('ultralightToggle');
const hideStaleToggle = $('hideStaleToggle');
const resetFiltersBtn = $('resetFiltersBtn');
const sortSelect = $('sortSelect');

const compareDock = $('compareDock');
const compareCount = $('compareCount');
const compareThumbnails = $('compareThumbnails');
const clearCompareBtn = $('clearCompareBtn');
const openCompareModalBtn = $('openCompareModalBtn');
const compareModal = $('compareModal');
const compareModalBody = $('compareModalBody');
const closeCompareModalBtn = $('closeCompareModalBtn');

const scraperStatusModal = $('scraperStatusModal');
const openStatusModalBtn = $('openStatusModalBtn');
const closeStatusModalBtn = $('closeStatusModalBtn');
const closeStatusModalFooterBtn = $('closeStatusModalFooterBtn');
const scraperStatusBody = $('scraperStatusBody');
const statusHeaderPill = $('statusHeaderPill');

/* --------------------------------------------------------------------------
   3. UTILITY FUNCTIONS
   -------------------------------------------------------------------------- */

function debounce(fn, delay = 120) {
  let timer;
  return function (...args) {
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, args), delay);
  };
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function parseDaysOld(scraped_at) {
  if (!scraped_at) return 0;
  const itemDate = new Date(scraped_at);
  if (isNaN(itemDate.getTime())) return 0;
  const diffTime = Math.abs(Date.now() - itemDate.getTime());
  return Math.floor(diffTime / (1000 * 60 * 60 * 24));
}

function getCpuGenRank(cpuStr) {
  if (!cpuStr) return 0;
  const s = String(cpuStr).toLowerCase();
  if (s.includes('m1') || s.includes('m2') || s.includes('m3') || s.includes('m4')) return 13;
  if (s.includes('13th') || s.includes('13-')) return 13;
  if (s.includes('12th') || s.includes('12-')) return 12;
  if (s.includes('11th') || s.includes('11-')) return 11;
  if (s.includes('10th') || s.includes('10-')) return 10;
  if (s.includes('9th') || s.includes('9-')) return 9;
  if (s.includes('8th') || s.includes('8-')) return 8;
  if (s.includes('ryzen 7') || s.includes('ryzen 5') || s.includes('ryzen 3') || s.includes('ryzen 9')) return 10;

  const iMatch = s.match(/i[3579]-?(\d{1,2})\d{3}/);
  if (iMatch && iMatch[1]) {
    const gen = parseInt(iMatch[1], 10);
    if (!isNaN(gen)) return gen;
  }
  return 0;
}

function matchesCpuGen(cpuStr, cpuGenVal, dir = 'up') {
  if (!cpuGenVal || cpuGenVal === 'all' || cpuGenVal === '0') return true;

  let targetGen = 0;
  let targetDir = dir;

  if (typeof cpuGenVal === 'string' && cpuGenVal.includes('-')) {
    const parts = cpuGenVal.split('-');
    targetGen = parseInt(parts[0], 10) || 0;
    targetDir = parts[1] || 'up';
  } else if (typeof cpuGenVal === 'number') {
    targetGen = cpuGenVal;
  } else {
    targetGen = parseInt(cpuGenVal, 10) || 0;
  }

  const rank = getCpuGenRank(cpuStr);
  if (targetDir === 'down') {
    return rank <= targetGen;
  }
  return rank >= targetGen;
}

function calculateValueScore(item) {
  if (!item) return 5.0;
  const price = Number(item.deal_price_ils || item.price_ils) || 1;
  const ram = Number(item.ram_gb) || 8;
  const ssd = Number(item.storage_gb) || 256;
  const cpuRank = item._cpuRank || getCpuGenRank(item.cpu);
  const upgrade = Number(item.upgradability_score) || 5;

  const specPoints = (ram * 12) + (ssd * 0.25) + (cpuRank * 20) + (upgrade * 8);
  let rawScore = (specPoints / price) * 120;
  if (rawScore > 9.9) rawScore = 9.9;
  if (rawScore < 4.0) rawScore = 4.0;
  return Math.round(rawScore * 10) / 10;
}

function cleanTitle(title, brand) {
  if (!title) return 'Refurbished Device';
  let clean = String(title);

  // Remove raw SKUs, trailing specs, repeated RAM/SSD
  clean = clean.replace(/\s*\(?(?:i[3579]|Ryzen\s*\d|Apple\s*M\d)\s*[\/\-,\s]*\d+\s*GB[\/\-,\s]*\d+\s*(?:GB|TB)?(?:\s*SSD)?\)?/gi, '');
  clean = clean.replace(/\s*\d+\s*GB\s*(?:RAM|DDR\d)?\s*[\/\-,\s]*\d+\s*(?:GB|TB)\s*(?:SSD|NVMe)?/gi, '');
  clean = clean.replace(/\s*\(?~?DDR\d?.*$/gi, '');
  clean = clean.replace(/\s*⚡.*$/gi, '');
  clean = clean.replace(/\s*\**נמכר\**/gi, '');
  clean = clean.replace(/\s*מחודש\s*/gi, ' ');
  clean = clean.replace(/\s*עודפים\s*/gi, ' ');
  clean = clean.trim();

  if (clean.length < 3) return title;
  return clean;
}

function getBrandBadgeTheme(brand) {
  const b = String(brand).toLowerCase();
  if (b.includes('lenovo') || b.includes('thinkpad')) {
    return 'bg-rose-50 dark:bg-rose-950/80 text-rose-700 dark:text-rose-400 border-rose-200 dark:border-rose-800/60';
  }
  if (b.includes('hp') || b.includes('elitebook') || b.includes('probook')) {
    return 'bg-sky-50 dark:bg-sky-950/80 text-sky-700 dark:text-sky-400 border-sky-200 dark:border-sky-800/60';
  }
  if (b.includes('dell') || b.includes('latitude') || b.includes('xps')) {
    return 'bg-indigo-50 dark:bg-indigo-950/80 text-indigo-700 dark:text-indigo-400 border-indigo-200 dark:border-indigo-800/60';
  }
  if (b.includes('apple') || b.includes('macbook') || b.includes('iphone') || b.includes('ipad')) {
    return 'bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 border-slate-300 dark:border-slate-700';
  }
  if (b.includes('samsung') || b.includes('galaxy')) {
    return 'bg-blue-50 dark:bg-blue-950/80 text-blue-700 dark:text-blue-400 border-blue-200 dark:border-blue-800/60';
  }
  return 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700';
}

/* --------------------------------------------------------------------------
   4. DATA NORMALIZATION & LOADING
   -------------------------------------------------------------------------- */

function normalizeLaptopItems(laptopsUnified) {
  return (laptopsUnified || []).map((laptop, index) => {
    const brand = laptop.brand || 'Other';
    const store = laptop.store || 'Refurbished Store';
    const deal_price_ils = Number(laptop.deal_price_ils || laptop.price_ils) || 0;
    const price_ils = Number(laptop.price_ils || laptop.deal_price_ils) || 0;
    const ram_gb = Number(laptop.ram_gb) || 0;
    const storage_gb = Number(laptop.storage_gb) || 0;
    const upgradability_score = Number(laptop.upgradability_score) || 5.0;
    const cpu = laptop.cpu || 'Intel Core / AMD';

    const scraped_at = laptop.scraped_at || '';
    const days_old = parseDaysOld(scraped_at);
    const is_stale = days_old > 30;

    const item = {
      id: `laptop-${index}-${store.replace(/\s+/g, '_')}`,
      category: 'laptops',
      title: laptop.title || laptop.model || 'Laptop Listing',
      brand,
      store,
      cpu,
      ram_gb,
      storage_gb,
      price_ils,
      deal_price_ils,
      deal_label: laptop.deal_label || `${deal_price_ils || price_ils || ''} ₪`,
      storage_type: laptop.storage_type || 'NVMe SSD',
      ram_type: laptop.ram_type || 'Standard',
      ram_gen: laptop.ram_gen || 'DDR4',
      upgradability_score,
      warranty_months: laptop.warranty_months || 12,
      is_touch: Boolean(laptop.is_touch),
      is_2in1: Boolean(laptop.is_2in1),
      url: laptop.url || '#',
      screen_size_in: Number(laptop.screen_size_in) || 14.0,
      weight_kg: Number(laptop.weight_kg) || 1.45,
      battery_wh: Number(laptop.battery_wh) || 50,
      confidence_level: laptop.confidence_level || 'verified',
      scraped_at,
      days_old,
      is_stale
    };

    item._cpuRank = getCpuGenRank(cpu);
    item.value_score = calculateValueScore(item);
    item._price = deal_price_ils || price_ils || 0;
    item._brandLower = brand.toLowerCase();

    const touchKeywords = item.is_touch || item.is_2in1 ? 'touch touchscreen טאץ טאצ' : '';
    const formKeywords = item.is_2in1 ? '2in1 convertible' : 'clamshell';
    item._searchIndex = `${item.title} ${brand} ${store} ${cpu} ${ram_gb}gb ${storage_gb}gb ${item.screen_size_in}inch ${item.weight_kg}kg ${touchKeywords} ${formKeywords}`.toLowerCase();

    return item;
  });
}

function normalizeMobileItems(mobileUnified) {
  return (mobileUnified || []).map((dev, index) => {
    const brand = dev.brand || 'Mobile';
    const store = dev.store || 'Refurbished Store';
    const deal_price_ils = Number(dev.deal_price_ils || dev.price_ils) || 0;
    const price_ils = Number(dev.price_ils || dev.deal_price_ils) || 0;
    const ram_gb = Number(dev.ram_gb) || 0;
    const storage_gb = Number(dev.storage_gb) || 0;

    const scraped_at = dev.scraped_at || '';
    const days_old = parseDaysOld(scraped_at);
    const is_stale = days_old > 30;

    const item = {
      id: `mobile-${index}-${store.replace(/\s+/g, '_')}`,
      category: 'phones',
      device_type: dev.device_type || 'phone',
      title: dev.title || dev.model || 'Mobile Device',
      brand,
      store,
      cpu: dev.device_type === 'tablet' ? 'Tablet Chipset' : 'Mobile SoC',
      ram_gb,
      storage_gb,
      price_ils,
      deal_price_ils,
      deal_label: dev.deal_label || `${deal_price_ils || price_ils || ''} ₪`,
      storage_type: 'Flash Storage',
      ram_type: 'LPDDR',
      ram_gen: 'Mobile',
      upgradability_score: 1.0,
      warranty_months: dev.warranty_months || 12,
      is_touch: true,
      is_2in1: dev.device_type === 'tablet',
      url: dev.url || '#',
      screen_size_in: Number(dev.screen_size_in) || (dev.device_type === 'tablet' ? 10.5 : 6.1),
      weight_kg: dev.device_type === 'tablet' ? 0.48 : 0.19,
      battery_wh: dev.device_type === 'tablet' ? 28 : 15,
      confidence_level: dev.confidence_level || 'verified',
      scraped_at,
      days_old,
      is_stale
    };

    item._cpuRank = 0;
    item.value_score = calculateValueScore(item);
    item._price = deal_price_ils || price_ils || 0;
    item._brandLower = brand.toLowerCase();
    item._searchIndex = `${item.title} ${brand} ${store} ${item.cpu} ${ram_gb}gb ${storage_gb}gb ${item.device_type}`.toLowerCase();

    return item;
  });
}

async function loadCatalogData() {
  try {
    let laptopsUnified = [];
    let res = await fetch('./data/scraped_laptops.json');
    if (!res.ok) res = await fetch('./scraped_laptops.json');
    if (res.ok) {
      const rawJson = await res.json();
      if (Array.isArray(rawJson)) laptopsUnified = rawJson;
      else if (typeof rawJson === 'object') {
        Object.keys(rawJson).forEach((key) => {
          if (Array.isArray(rawJson[key])) laptopsUnified = laptopsUnified.concat(rawJson[key]);
        });
      }
    }

    const laptopItems = normalizeLaptopItems(laptopsUnified);
    state.catalogData = laptopItems;

    // Async load mobile items in parallel
    loadMobileData();

    populateStoreSelectOptions();
    applyCatalogFilters();
  } catch (err) {
    console.error('Failed to load scraped_laptops.json', err);
    if (catalogContent) {
      catalogContent.innerHTML = `<div class="p-8 text-center text-rose-500">Failed to load catalog dataset. Please try refreshing.</div>`;
    }
  }
}

async function loadMobileData() {
  try {
    let mobileUnified = [];
    let res = await fetch('./data/scraped_mobile.json');
    if (!res.ok) res = await fetch('./scraped_mobile.json');
    if (res.ok) {
      const rawJson = await res.json();
      if (Array.isArray(rawJson)) mobileUnified = rawJson;
      else if (typeof rawJson === 'object') {
        Object.keys(rawJson).forEach((key) => {
          if (Array.isArray(rawJson[key])) mobileUnified = mobileUnified.concat(rawJson[key]);
        });
      }
    }

    const mobileItems = normalizeMobileItems(mobileUnified);
    const nonMobile = state.catalogData.filter((i) => i.category !== 'phones');
    state.catalogData = [...nonMobile, ...mobileItems];

    populateStoreSelectOptions();
    if (state.catalogFilters.category === 'phones') {
      applyCatalogFilters();
    }
  } catch (err) {
    console.warn('Failed to load scraped_mobile.json', err);
  }
}

function populateStoreSelectOptions() {
  if (!storeSelect) return;
  const currentVal = storeSelect.value;
  const storesSet = new Set(state.catalogData.map((item) => item.store).filter(Boolean));
  const sortedStores = Array.from(storesSet).sort();

  let html = `<option value="all">All Certified Stores (${sortedStores.length})</option>`;
  sortedStores.forEach((store) => {
    html += `<option value="${escapeHtml(store)}">${escapeHtml(store)}</option>`;
  });
  storeSelect.innerHTML = html;
  if (storesSet.has(currentVal)) {
    storeSelect.value = currentVal;
  }
}

/* --------------------------------------------------------------------------
   5. FILTERING & SORTING LOGIC
   -------------------------------------------------------------------------- */

function applyCatalogFilters() {
  const f = state.catalogFilters;
  const queryLower = state.query.trim().toLowerCase();

  currentFilteredItems = state.catalogData.filter((item) => {
    // Category filter
    if (f.category === 'all' && item.category === 'phones') return false; // Default 'all' shows laptops
    if (f.category === 'phones' && item.category !== 'phones') return false;

    // Store filter
    if (f.store !== 'all' && item.store !== f.store) return false;

    // Price filter
    if (f.priceMax > 0 && item._price > f.priceMax) return false;

    // Brand filter
    if (f.brands.length > 0 && !f.brands.includes('all')) {
      const matchBrand = f.brands.some((b) => item._brandLower.includes(b.toLowerCase()));
      if (!matchBrand) return false;
    }

    // RAM filter
    if (f.ramMin > 0 && item.ram_gb < f.ramMin) return false;

    // Storage filter
    if (f.storageMin > 0 && item.storage_gb < f.storageMin) return false;

    // CPU Generation threshold (laptops)
    if (f.cpuGenMin > 0 && item.category === 'laptops') {
      if (item._cpuRank < f.cpuGenMin) return false;
    }

    // Hardware Must-Haves
    if (f.swappableRamOnly && item.upgradability_score < 7.0) return false;
    if (f.ultralightOnly && item.weight_kg > 1.4) return false;
    if (f.hideStale && item.is_stale) return false;

    // Query search
    if (queryLower && !item._searchIndex.includes(queryLower)) return false;

    return true;
  });

  // Calculate Top Value threshold for badge highlighting
  const topScored = [...currentFilteredItems].sort((a, b) => b.value_score - a.value_score);
  const top15Percent = Math.max(1, Math.floor(topScored.length * 0.15));
  currentTopValueIds = new Set(topScored.slice(0, top15Percent).map((i) => i.id));

  // Sort items
  currentFilteredItems.sort((a, b) => {
    if (f.sort === 'price-asc') return a._price - b._price;
    if (f.sort === 'price-desc') return b._price - a._price;
    if (f.sort === 'ram-desc') return b.ram_gb - a.ram_gb;
    if (f.sort === 'storage-desc') return b.storage_gb - a.storage_gb;
    if (f.sort === 'weight-asc') return a.weight_kg - b.weight_kg;
    return b.value_score - a.value_score; // Default 'value-desc'
  });

  renderedCount = 0;
  renderCatalogView();
}

/* --------------------------------------------------------------------------
   6. RENDERING: CARDS & TABLE VIEWS
   -------------------------------------------------------------------------- */

function renderCardHtml(item) {
  const isTopValue = currentTopValueIds.has(item.id);
  const brandBadgeClass = getBrandBadgeTheme(item.brand);
  const cleanedTitle = cleanTitle(item.title, item.brand);
  const isCompared = state.comparedIds.has(item.id);

  // Form factor / sublabel
  let formFactorStr = item.category === 'phones'
    ? (item.device_type === 'tablet' ? 'Tablet' : 'Smartphone')
    : (item.is_2in1 ? '2-in-1 Touchscreen' : 'Clamshell Notebook');
  let sublabel = `${formFactorStr} • Grade A • ${item.warranty_months}M Warranty`;

  // Specs 2x2 grid values
  const cpuText = escapeHtml(item.cpu || 'Multi-Core Processor');
  const ramText = item.ram_gb ? `${item.ram_gb} GB ${item.ram_gen || ''}` : 'Standard Memory';
  const storageText = item.storage_gb ? `${item.storage_gb} GB ${item.storage_type || ''}` : 'Internal SSD';
  const displayWeightText = `${item.screen_size_in ? item.screen_size_in + '"' : ''} ${item.weight_kg ? '| ~' + item.weight_kg + ' kg' : ''}`;

  // Upgradability / Modularity bar
  let modularityHtml = '';
  if (item.category === 'laptops') {
    const isModular = item.upgradability_score >= 7.0;
    modularityHtml = `
      <div class="mt-3 pt-2.5 border-t border-slate-100 dark:border-slate-800/60 flex items-center justify-between text-[11px]">
        <span class="text-slate-500 dark:text-slate-400 flex items-center gap-1">
          ${isModular ? '🛠️ Modular SODIMM (Upgradable)' : '🔒 Integrated / Ultrabook'}
        </span>
        <span class="font-mono font-semibold ${isModular ? 'text-emerald-600 dark:text-emerald-400' : 'text-slate-400'}">
          Upgradability ${item.upgradability_score}/10
        </span>
      </div>`;
  } else {
    modularityHtml = `
      <div class="mt-3 pt-2.5 border-t border-slate-100 dark:border-slate-800/60 flex items-center justify-between text-[11px]">
        <span class="text-slate-500 dark:text-slate-400 flex items-center gap-1">📱 Mobile Architecture</span>
        <span class="font-mono text-slate-400">Fixed Capacity</span>
      </div>`;
  }

  return `
    <div class="bg-white dark:bg-slate-900 rounded-2xl p-5 border border-slate-200 dark:border-slate-800 hover:border-indigo-300 dark:hover:border-indigo-700 shadow-sm hover:shadow-md transition-all group flex flex-col justify-between">
      <div>
        <!-- Card Header: Badges & Value Score -->
        <div class="flex items-start justify-between gap-2 mb-3">
          <div class="flex flex-wrap items-center gap-1.5">
            <span class="badge-chip px-2.5 py-0.5 text-[11px] font-semibold rounded-full border ${brandBadgeClass}">
              ${escapeHtml(item.brand)}
            </span>
            <span class="badge-chip px-2.5 py-0.5 text-[11px] font-medium rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-700">
              ${escapeHtml(item.store)}
            </span>
            ${isTopValue ? `<span class="badge-chip px-2 py-0.5 text-[10px] font-bold uppercase rounded-full bg-amber-100 dark:bg-amber-950/80 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-800">Best Value</span>` : ''}
          </div>

          <div class="px-2 py-0.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/80 text-emerald-700 dark:text-emerald-400 font-mono text-xs font-bold border border-emerald-200 dark:border-emerald-800/60 shrink-0">
            ★ ${item.value_score}
          </div>
        </div>

        <!-- Clean Device Title & Sublabel -->
        <h3 class="font-bold text-slate-900 dark:text-white text-base leading-snug group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition line-clamp-2">
          ${escapeHtml(cleanedTitle)}
        </h3>
        <p class="text-xs text-slate-500 dark:text-slate-400 mt-1 mb-4">${escapeHtml(sublabel)}</p>

        <!-- Specs Grid 2x2 Layout -->
        <div class="grid grid-cols-2 gap-2 bg-slate-50 dark:bg-slate-950/60 p-3 rounded-xl border border-slate-100 dark:border-slate-800 text-xs">
          <div>
            <div class="text-[10px] uppercase font-semibold text-slate-400">Processor</div>
            <div class="font-medium text-slate-800 dark:text-slate-200 truncate" title="${cpuText}">⚡ ${cpuText}</div>
          </div>
          <div>
            <div class="text-[10px] uppercase font-semibold text-slate-400">Memory</div>
            <div class="font-medium text-slate-800 dark:text-slate-200 truncate">${escapeHtml(ramText)}</div>
          </div>
          <div>
            <div class="text-[10px] uppercase font-semibold text-slate-400">Storage</div>
            <div class="font-medium text-slate-800 dark:text-slate-200 truncate">${escapeHtml(storageText)}</div>
          </div>
          <div>
            <div class="text-[10px] uppercase font-semibold text-slate-400">Display / Weight</div>
            <div class="font-medium text-slate-800 dark:text-slate-200 truncate">${escapeHtml(displayWeightText)}</div>
          </div>
        </div>

        ${modularityHtml}
      </div>

      <!-- Card Footer: Price & Actions -->
      <div class="mt-5 pt-3 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between gap-3">
        <div>
          <div class="text-xs text-slate-400">Price</div>
          <div class="font-mono font-extrabold text-lg text-slate-900 dark:text-white">
            ₪${item._price.toLocaleString()}
          </div>
        </div>

        <div class="flex items-center gap-2">
          <button
            type="button"
            onclick="toggleCompare('${item.id}')"
            class="p-2 rounded-xl border transition ${isCompared ? 'bg-indigo-600 text-white border-indigo-600' : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 border-slate-200 dark:border-slate-700 hover:border-indigo-400'}"
            title="${isCompared ? 'Remove from compare' : 'Add to compare'}"
          >
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 002 2h2a2 2 0 002-2z"/>
            </svg>
          </button>
          <a
            href="${escapeHtml(item.url)}"
            target="_blank"
            rel="noopener noreferrer"
            class="px-3 py-2 rounded-xl bg-slate-900 hover:bg-indigo-600 dark:bg-white dark:hover:bg-indigo-500 text-white dark:text-slate-900 dark:hover:text-white font-medium text-xs transition shadow-xs flex items-center gap-1"
          >
            View Store ↗
          </a>
        </div>
      </div>
    </div>`;
}

function renderTableHtml(items) {
  if (!items || items.length === 0) return '';

  const rowsHtml = items.map((item) => {
    const cleanedTitle = cleanTitle(item.title, item.brand);
    const isCompared = state.comparedIds.has(item.id);

    return `
      <tr class="border-b border-slate-100 dark:border-slate-800/80 hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition">
        <td class="py-3 px-4">
          <div class="font-bold text-slate-900 dark:text-white text-xs">${escapeHtml(cleanedTitle)}</div>
          <div class="text-[10px] text-slate-400">${escapeHtml(item.brand)} • ${escapeHtml(item.store)}</div>
        </td>
        <td class="py-3 px-4 font-mono text-xs text-slate-700 dark:text-slate-300 truncate max-w-[140px]">${escapeHtml(item.cpu)}</td>
        <td class="py-3 px-4 font-mono text-xs text-slate-700 dark:text-slate-300">${item.ram_gb ? item.ram_gb + ' GB' : 'N/A'}</td>
        <td class="py-3 px-4 font-mono text-xs text-slate-700 dark:text-slate-300">${item.storage_gb ? item.storage_gb + ' GB' : 'N/A'}</td>
        <td class="py-3 px-4 font-mono text-xs text-slate-700 dark:text-slate-300">${item.screen_size_in ? item.screen_size_in + '"' : ''} ${item.weight_kg ? '(' + item.weight_kg + 'kg)' : ''}</td>
        <td class="py-3 px-4 font-mono text-xs text-slate-700 dark:text-slate-300">${item.category === 'laptops' ? item.upgradability_score + '/10' : 'Fixed'}</td>
        <td class="py-3 px-4 font-mono text-xs font-bold text-emerald-600 dark:text-emerald-400">★ ${item.value_score}</td>
        <td class="py-3 px-4 font-mono text-xs font-extrabold text-slate-900 dark:text-white">₪${item._price.toLocaleString()}</td>
        <td class="py-3 px-4 flex items-center gap-2">
          <button onclick="toggleCompare('${item.id}')" class="p-1.5 rounded-lg border text-xs ${isCompared ? 'bg-indigo-600 text-white' : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300'}" title="Compare">📊</button>
          <a href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer" class="px-2.5 py-1 rounded-lg bg-slate-900 text-white dark:bg-white dark:text-slate-900 text-xs font-semibold hover:bg-indigo-600 transition">Store ↗</a>
        </td>
      </tr>`;
  }).join('');

  return `
    <div class="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-x-auto">
      <table class="w-full text-left border-collapse">
        <thead>
          <tr class="bg-slate-50 dark:bg-slate-950/60 border-b border-slate-200 dark:border-slate-800 text-[11px] uppercase tracking-wider text-slate-400 font-semibold">
            <th class="py-3 px-4">Model & Store</th>
            <th class="py-3 px-4">CPU / SoC</th>
            <th class="py-3 px-4">RAM</th>
            <th class="py-3 px-4">Storage</th>
            <th class="py-3 px-4">Display / Weight</th>
            <th class="py-3 px-4">Upgradability</th>
            <th class="py-3 px-4">Value</th>
            <th class="py-3 px-4">Price</th>
            <th class="py-3 px-4">Action</th>
          </tr>
        </thead>
        <tbody>
          ${rowsHtml}
        </tbody>
      </table>
    </div>`;
}

function renderCatalogView() {
  if (!catalogContent) return;

  // Update results counter
  if (resultsCount) {
    const total = currentFilteredItems.length;
    const catLabel = state.catalogFilters.category === 'phones' ? 'mobile devices' : 'laptops';
    resultsCount.textContent = `Showing ${total} ${catLabel}`;
  }

  if (currentFilteredItems.length === 0) {
    catalogContent.innerHTML = `
      <div class="bg-white dark:bg-slate-900 rounded-2xl p-12 border border-slate-200 dark:border-slate-800 text-center space-y-4">
        <div class="text-4xl">🔍</div>
        <h3 class="font-bold text-lg text-slate-900 dark:text-white">No matching listings found</h3>
        <p class="text-sm text-slate-500 max-w-md mx-auto">Try adjusting your price range, RAM thresholds, or search keywords to broaden your search.</p>
        <button onclick="resetAllFilters()" class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs rounded-xl shadow-md transition">Reset All Filters</button>
      </div>`;
    return;
  }

  if (state.viewMode === 'table') {
    catalogContent.innerHTML = renderTableHtml(currentFilteredItems);
    return;
  }

  // Grid View rendering
  const batch = currentFilteredItems.slice(0, PAGE_SIZE);
  renderedCount = batch.length;

  let gridHtml = `<div id="cardsGrid" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">`;
  batch.forEach((item) => {
    gridHtml += renderCardHtml(item);
  });
  gridHtml += `</div>`;

  if (renderedCount < currentFilteredItems.length) {
    gridHtml += `
      <div id="loadMoreTrigger" class="py-8 text-center text-xs text-slate-400">
        Showing ${renderedCount} of ${currentFilteredItems.length} listings...
      </div>`;
  }

  catalogContent.innerHTML = gridHtml;
  setupCatalogObserver();
}

function loadMoreCatalogCards() {
  if (renderedCount >= currentFilteredItems.length) return;
  const cardsGrid = document.getElementById('cardsGrid');
  if (!cardsGrid) return;

  const nextBatch = currentFilteredItems.slice(renderedCount, renderedCount + PAGE_SIZE);
  renderedCount += nextBatch.length;

  nextBatch.forEach((item) => {
    cardsGrid.insertAdjacentHTML('beforeend', renderCardHtml(item));
  });

  const trigger = document.getElementById('loadMoreTrigger');
  if (trigger) {
    if (renderedCount >= currentFilteredItems.length) {
      trigger.remove();
    } else {
      trigger.textContent = `Showing ${renderedCount} of ${currentFilteredItems.length} listings...`;
    }
  }
}

function setupCatalogObserver() {
  if (catalogObserver) catalogObserver.disconnect();
  const trigger = document.getElementById('loadMoreTrigger');
  if (!trigger) return;

  catalogObserver = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting) {
      loadMoreCatalogCards();
    }
  }, { rootMargin: '200px' });

  catalogObserver.observe(trigger);
}

/* --------------------------------------------------------------------------
   7. COMPARISON DOCK & MODAL
   -------------------------------------------------------------------------- */

const toggleCompare = (typeof window !== 'undefined' ? window : global).toggleCompare = function (id) {
  if (state.comparedIds.has(id)) {
    state.comparedIds.delete(id);
  } else {
    if (state.comparedIds.size >= 3) {
      alert('You can compare up to 3 devices simultaneously.');
      return;
    }
    state.comparedIds.add(id);
  }
  updateCompareDockUI();
  renderCatalogView();
};

function updateCompareDockUI() {
  if (!compareDock) return;
  const count = state.comparedIds.size;
  if (compareCount) compareCount.textContent = count;

  if (count === 0) {
    compareDock.classList.add('translate-y-32', 'opacity-0', 'pointer-events-none');
    compareDock.classList.remove('translate-y-0', 'opacity-100', 'pointer-events-auto');
    return;
  }

  // Build thumbnails
  let thumbsHtml = '';
  state.comparedIds.forEach((id) => {
    const item = state.catalogData.find((i) => i.id === id);
    if (!item) return;
    thumbsHtml += `
      <div class="flex items-center gap-1.5 bg-slate-800 px-2.5 py-1 rounded-xl text-xs border border-slate-700">
        <span class="font-semibold text-slate-200 max-w-[100px] truncate">${escapeHtml(cleanTitle(item.title, item.brand))}</span>
        <button onclick="toggleCompare('${id}')" class="text-slate-400 hover:text-white text-xs">✕</button>
      </div>`;
  });
  if (compareThumbnails) compareThumbnails.innerHTML = thumbsHtml;

  compareDock.classList.remove('translate-y-32', 'opacity-0', 'pointer-events-none');
  compareDock.classList.add('translate-y-0', 'opacity-100', 'pointer-events-auto');
}

function renderCompareModalMatrix() {
  if (!compareModalBody) return;

  const items = Array.from(state.comparedIds).map((id) => state.catalogData.find((i) => i.id === id)).filter(Boolean);
  if (items.length === 0) {
    compareModalBody.innerHTML = `<div class="text-center py-8 text-slate-400">No devices selected for comparison.</div>`;
    return;
  }

  let html = `<div class="grid grid-cols-${items.length} gap-4">`;
  items.forEach((item) => {
    html += `
      <div class="bg-slate-50 dark:bg-slate-950/60 p-4 rounded-xl border border-slate-200 dark:border-slate-800 space-y-3 text-xs">
        <div>
          <span class="text-[10px] uppercase font-bold text-indigo-500">${escapeHtml(item.brand)} • ${escapeHtml(item.store)}</span>
          <h4 class="font-bold text-sm text-slate-900 dark:text-white mt-1">${escapeHtml(cleanTitle(item.title, item.brand))}</h4>
        </div>

        <div class="font-mono text-base font-extrabold text-indigo-600 dark:text-indigo-400">₪${item._price.toLocaleString()}</div>

        <div class="space-y-1.5 pt-2 border-t border-slate-200 dark:border-slate-800">
          <div><strong class="text-slate-400">Value Rating:</strong> ★ ${item.value_score}/10</div>
          <div><strong class="text-slate-400">CPU:</strong> ${escapeHtml(item.cpu)}</div>
          <div><strong class="text-slate-400">RAM:</strong> ${item.ram_gb ? item.ram_gb + ' GB ' + (item.ram_gen || '') : 'N/A'}</div>
          <div><strong class="text-slate-400">Storage:</strong> ${item.storage_gb ? item.storage_gb + ' GB ' + (item.storage_type || '') : 'N/A'}</div>
          <div><strong class="text-slate-400">Display:</strong> ${item.screen_size_in ? item.screen_size_in + '"' : 'N/A'}</div>
          <div><strong class="text-slate-400">Weight:</strong> ${item.weight_kg ? item.weight_kg + ' kg' : 'N/A'}</div>
          <div><strong class="text-slate-400">Upgradability:</strong> ${item.category === 'laptops' ? item.upgradability_score + '/10' : 'Integrated'}</div>
          <div><strong class="text-slate-400">Warranty:</strong> ${item.warranty_months} Months</div>
        </div>

        <a href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer" class="block text-center py-2 bg-indigo-600 text-white rounded-lg font-semibold transition hover:bg-indigo-500 mt-3">View Store Listing ↗</a>
      </div>`;
  });
  html += `</div>`;

  compareModalBody.innerHTML = html;
}

/* --------------------------------------------------------------------------
   8. MARKDOWN GUIDE RENDERER
   -------------------------------------------------------------------------- */

async function loadGuideDocument() {
  if (!documentContent) return;
  try {
    let res = await fetch('./data/full_catalog.md');
    if (!res.ok) res = await fetch('./full_catalog.md');
    if (res.ok) {
      const rawMd = await res.text();
      const cleanHtml = DOMPurify.sanitize(marked.parse(rawMd));
      documentContent.innerHTML = cleanHtml;
    }
  } catch (err) {
    console.error('Failed to load full_catalog.md', err);
  }
}

/* --------------------------------------------------------------------------
   9. SCRAPER STATUS MODAL
   -------------------------------------------------------------------------- */

async function openScraperStatusModal() {
  if (!scraperStatusModal) return;
  scraperStatusModal.style.display = 'flex';

  if (!scraperStatusBody) return;
  scraperStatusBody.innerHTML = `<div class="text-center py-4 text-xs text-slate-400">Loading store health telemetry...</div>`;

  try {
    let res = await fetch('./data/scraper_status.json');
    if (!res.ok) res = await fetch('./scraper_status.json');
    if (res.ok) {
      const data = await res.json();
      let html = `<div class="space-y-3">`;
      if (data.stores && typeof data.stores === 'object') {
        Object.keys(data.stores).forEach((storeKey) => {
          const st = data.stores[storeKey];
          const isOk = st.status === 'ok' || st.status === 'success';
          html += `
            <div class="flex items-center justify-between p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-800 text-xs">
              <div class="flex items-center gap-2">
                <span class="w-2 h-2 rounded-full ${isOk ? 'bg-emerald-500' : 'bg-amber-500'}"></span>
                <span class="font-bold text-slate-800 dark:text-slate-200">${escapeHtml(st.name || storeKey)}</span>
              </div>
              <div class="font-mono text-slate-500">
                ${st.count || 0} items • ${st.last_run || 'Synced'}
              </div>
            </div>`;
        });
      }
      html += `</div>`;
      scraperStatusBody.innerHTML = html;
    }
  } catch (err) {
    scraperStatusBody.innerHTML = `<div class="text-center py-4 text-xs text-slate-400">Telemetry currently active across live feeds.</div>`;
  }
}

/* --------------------------------------------------------------------------
   10. EVENT BINDINGS & CONTROLS
   -------------------------------------------------------------------------- */

const resetAllFilters = (typeof window !== 'undefined' ? window : global).resetAllFilters = function () {
  state.query = '';
  state.activePreset = 'all';
  state.catalogFilters = {
    category: 'all',
    store: 'all',
    brands: [],
    priceMax: 5000,
    ramMin: 0,
    storageMin: 0,
    cpuGenMin: 0,
    swappableRamOnly: false,
    ultralightOnly: false,
    hideStale: false,
    sort: 'value-desc'
  };

  if (searchInput) searchInput.value = '';
  if (mobileSearchInput) mobileSearchInput.value = '';
  if (storeSelect) storeSelect.value = 'all';
  if (priceSlider) priceSlider.value = 5000;
  if (priceOutput) priceOutput.textContent = '₪ 5,000';
  if (cpuGenSelect) cpuGenSelect.value = '0';
  if (sortSelect) sortSelect.value = 'value-desc';
  if (swappableRamToggle) swappableRamToggle.checked = false;
  if (ultralightToggle) ultralightToggle.checked = false;
  if (hideStaleToggle) hideStaleToggle.checked = false;

  updateFilterPillsUI();
  applyCatalogFilters();
};

function updateFilterPillsUI() {
  // Category chips
  if (categoryChips) {
    categoryChips.querySelectorAll('.category-chip').forEach((btn) => {
      const cat = btn.getAttribute('data-category');
      if (cat === state.catalogFilters.category) {
        btn.className = 'category-chip active py-1.5 text-xs text-center rounded-lg font-medium bg-slate-900 text-white dark:bg-white dark:text-slate-900 transition';
      } else {
        btn.className = 'category-chip py-1.5 text-xs text-center rounded-lg font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 transition';
      }
    });
  }

  // Brand chips
  if (brandPills) {
    brandPills.querySelectorAll('.brand-chip').forEach((btn) => {
      const brand = btn.getAttribute('data-brand');
      const isSelected = state.catalogFilters.brands.includes(brand) || (brand === 'all' && state.catalogFilters.brands.length === 0);
      if (isSelected) {
        btn.className = 'brand-chip active px-2.5 py-1 text-xs rounded-lg font-medium bg-slate-900 text-white dark:bg-white dark:text-slate-900 transition';
      } else {
        btn.className = 'brand-chip px-2.5 py-1 text-xs rounded-lg font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 transition';
      }
    });
  }

  // RAM chips
  if (ramPills) {
    ramPills.querySelectorAll('.ram-chip').forEach((btn) => {
      const ram = Number(btn.getAttribute('data-ram'));
      if (ram === state.catalogFilters.ramMin) {
        btn.className = 'ram-chip active py-1.5 text-xs text-center rounded-lg font-medium bg-slate-900 text-white dark:bg-white dark:text-slate-900 transition';
      } else {
        btn.className = 'ram-chip py-1.5 text-xs text-center rounded-lg font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 transition';
      }
    });
  }

  // Storage chips
  if (storagePills) {
    storagePills.querySelectorAll('.ssd-chip').forEach((btn) => {
      const ssd = Number(btn.getAttribute('data-ssd'));
      if (ssd === state.catalogFilters.storageMin) {
        btn.className = 'ssd-chip active py-1.5 text-xs text-center rounded-lg font-medium bg-slate-900 text-white dark:bg-white dark:text-slate-900 transition';
      } else {
        btn.className = 'ssd-chip py-1.5 text-xs text-center rounded-lg font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 transition';
      }
    });
  }

  // Presets
  if (typeof document !== 'undefined') {
    document.querySelectorAll('.preset-btn').forEach((btn) => {
      const preset = btn.getAttribute('data-preset');
      if (preset === state.activePreset) {
        btn.className = 'preset-btn active px-3 py-1.5 rounded-full font-medium bg-slate-900 text-white dark:bg-white dark:text-slate-900 shadow-xs shrink-0 transition';
      } else {
        btn.className = 'preset-btn px-3 py-1.5 rounded-full font-medium bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700 hover:border-indigo-400 dark:hover:border-indigo-500 shrink-0 transition';
      }
    });
  }
}

function bindEvents() {
  if (typeof document === 'undefined') return;

  // Search input listeners (with '/' keyboard shortcut focus)
  const onSearch = debounce((val) => {
    state.query = val;
    applyCatalogFilters();
  }, 150);

  if (searchInput) {
    searchInput.addEventListener('input', (e) => onSearch(e.target.value));
  }
  if (mobileSearchInput) {
    mobileSearchInput.addEventListener('input', (e) => onSearch(e.target.value));
  }

  document.addEventListener('keydown', (e) => {
    if (e.key === '/' && document.activeElement !== searchInput && document.activeElement !== mobileSearchInput) {
      e.preventDefault();
      if (searchInput) searchInput.focus();
    }
  });

  // Category switch (Laptops vs Mobile)
  if (categoryChips) {
    categoryChips.addEventListener('click', (e) => {
      const btn = e.target.closest('.category-chip');
      if (!btn) return;
      state.catalogFilters.category = btn.getAttribute('data-category');

      if (cpuGenGroup) {
        if (state.catalogFilters.category === 'phones') {
          cpuGenGroup.style.display = 'none';
        } else {
          cpuGenGroup.style.display = 'block';
        }
      }

      updateFilterPillsUI();
      applyCatalogFilters();
    });
  }

  // Store select
  if (storeSelect) {
    storeSelect.addEventListener('change', (e) => {
      state.catalogFilters.store = e.target.value;
      applyCatalogFilters();
    });
  }

  // Price slider
  if (priceSlider) {
    priceSlider.addEventListener('input', (e) => {
      const val = Number(e.target.value);
      state.catalogFilters.priceMax = val;
      if (priceOutput) priceOutput.textContent = `₪ ${val.toLocaleString()}`;
      applyCatalogFilters();
    });
  }

  // Brand pills
  if (brandPills) {
    brandPills.addEventListener('click', (e) => {
      const btn = e.target.closest('.brand-chip');
      if (!btn) return;
      const brand = btn.getAttribute('data-brand');
      if (brand === 'all') {
        state.catalogFilters.brands = [];
      } else {
        state.catalogFilters.brands = [brand];
      }
      updateFilterPillsUI();
      applyCatalogFilters();
    });
  }

  // RAM pills
  if (ramPills) {
    ramPills.addEventListener('click', (e) => {
      const btn = e.target.closest('.ram-chip');
      if (!btn) return;
      state.catalogFilters.ramMin = Number(btn.getAttribute('data-ram'));
      updateFilterPillsUI();
      applyCatalogFilters();
    });
  }

  // Storage pills
  if (storagePills) {
    storagePills.addEventListener('click', (e) => {
      const btn = e.target.closest('.ssd-chip');
      if (!btn) return;
      state.catalogFilters.storageMin = Number(btn.getAttribute('data-ssd'));
      updateFilterPillsUI();
      applyCatalogFilters();
    });
  }

  // CPU Gen select
  if (cpuGenSelect) {
    cpuGenSelect.addEventListener('change', (e) => {
      state.catalogFilters.cpuGenMin = Number(e.target.value);
      applyCatalogFilters();
    });
  }

  // Feature toggles
  if (swappableRamToggle) {
    swappableRamToggle.addEventListener('change', (e) => {
      state.catalogFilters.swappableRamOnly = e.target.checked;
      applyCatalogFilters();
    });
  }
  if (ultralightToggle) {
    ultralightToggle.addEventListener('change', (e) => {
      state.catalogFilters.ultralightOnly = e.target.checked;
      applyCatalogFilters();
    });
  }
  if (hideStaleToggle) {
    hideStaleToggle.addEventListener('change', (e) => {
      state.catalogFilters.hideStale = e.target.checked;
      applyCatalogFilters();
    });
  }

  // Reset button
  if (resetFiltersBtn) {
    resetFiltersBtn.addEventListener('click', () => resetAllFilters());
  }

  // Sort select
  if (sortSelect) {
    sortSelect.addEventListener('change', (e) => {
      state.catalogFilters.sort = e.target.value;
      applyCatalogFilters();
    });
  }

  // Presets
  document.querySelectorAll('.preset-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const preset = btn.getAttribute('data-preset');
      state.activePreset = preset;

      if (preset === 'all') {
        resetAllFilters();
        return;
      }

      if (preset === 'value') {
        state.catalogFilters.sort = 'value-desc';
      } else if (preset === 'budget') {
        state.catalogFilters.priceMax = 1500;
        if (priceSlider) priceSlider.value = 1500;
        if (priceOutput) priceOutput.textContent = '₪ 1,500';
      } else if (preset === 'modular') {
        state.catalogFilters.swappableRamOnly = true;
        if (swappableRamToggle) swappableRamToggle.checked = true;
      } else if (preset === 'feather') {
        state.catalogFilters.ultralightOnly = true;
        if (ultralightToggle) ultralightToggle.checked = true;
      } else if (preset === 'workstation') {
        state.catalogFilters.ramMin = 32;
      }

      updateFilterPillsUI();
      applyCatalogFilters();
    });
  });

  // View Mode toggles
  if (viewToggleGrid) {
    viewToggleGrid.addEventListener('click', () => {
      state.viewMode = 'grid';
      state.filter = 'catalog';
      if (documentContent) documentContent.classList.add('hidden');
      if (catalogContent) catalogContent.classList.remove('hidden');
      viewToggleGrid.className = 'px-2.5 py-1 rounded-lg text-xs font-semibold bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-xs transition flex items-center gap-1';
      viewToggleTable.className = 'px-2.5 py-1 rounded-lg text-xs font-semibold text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200 transition flex items-center gap-1';
      renderCatalogView();
    });
  }

  if (viewToggleTable) {
    viewToggleTable.addEventListener('click', () => {
      state.viewMode = 'table';
      state.filter = 'catalog';
      if (documentContent) documentContent.classList.add('hidden');
      if (catalogContent) catalogContent.classList.remove('hidden');
      viewToggleTable.className = 'px-2.5 py-1 rounded-lg text-xs font-semibold bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-xs transition flex items-center gap-1';
      viewToggleGrid.className = 'px-2.5 py-1 rounded-lg text-xs font-semibold text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200 transition flex items-center gap-1';
      renderCatalogView();
    });
  }

  if (viewToggleGuide) {
    viewToggleGuide.addEventListener('click', () => {
      state.filter = 'guide';
      if (catalogContent) catalogContent.classList.add('hidden');
      if (documentContent) documentContent.classList.remove('hidden');
      loadGuideDocument();
    });
  }

  // Theme toggle
  if (themeToggle) {
    themeToggle.addEventListener('click', () => {
      const htmlEl = document.documentElement;
      if (htmlEl.classList.contains('dark')) {
        htmlEl.classList.remove('dark');
        localStorage.setItem('theme', 'light');
      } else {
        htmlEl.classList.add('dark');
        localStorage.setItem('theme', 'dark');
      }
    });
  }

  // Scraper status modal
  if (openStatusModalBtn) {
    openStatusModalBtn.addEventListener('click', openScraperStatusModal);
  }
  if (closeStatusModalBtn) {
    closeStatusModalBtn.addEventListener('click', () => { if (scraperStatusModal) scraperStatusModal.style.display = 'none'; });
  }
  if (closeStatusModalFooterBtn) {
    closeStatusModalFooterBtn.addEventListener('click', () => { if (scraperStatusModal) scraperStatusModal.style.display = 'none'; });
  }

  // Compare dock & modal
  if (clearCompareBtn) {
    clearCompareBtn.addEventListener('click', () => {
      state.comparedIds.clear();
      updateCompareDockUI();
      renderCatalogView();
    });
  }
  if (openCompareModalBtn) {
    openCompareModalBtn.addEventListener('click', () => {
      renderCompareModalMatrix();
      if (compareModal) compareModal.style.display = 'flex';
    });
  }
  if (closeCompareModalBtn) {
    closeCompareModalBtn.addEventListener('click', () => {
      if (compareModal) compareModal.style.display = 'none';
    });
  }

  // Export CSV
  if (exportCsvBtn) {
    exportCsvBtn.addEventListener('click', () => {
      if (currentFilteredItems.length === 0) return;
      let csv = 'Brand,Model,Store,Price (ILS),CPU,RAM (GB),Storage (GB),Value Score,URL\n';
      currentFilteredItems.forEach((i) => {
        csv += `"${i.brand}","${i.title.replace(/"/g, '""')}","${i.store}",${i._price},"${i.cpu}",${i.ram_gb},${i.storage_gb},${i.value_score},"${i.url}"\n`;
      });
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `second_hand_pc_hub_export.csv`;
      a.click();
    });
  }
}

/* --------------------------------------------------------------------------
   11. INITIALIZATION
   -------------------------------------------------------------------------- */

async function init() {
  if (typeof document === 'undefined') return;
  const savedTheme = localStorage.getItem('theme');
  if (savedTheme === 'dark' || (!savedTheme && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
    document.documentElement.classList.add('dark');
  } else {
    document.documentElement.classList.remove('dark');
  }

  bindEvents();
  await loadCatalogData();
}

if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', init);
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    calculateValueScore,
    matchesCpuGen,
    parseDaysOld,
    getCpuGenRank,
    cleanTitle,
    escapeHtml
  };
}
