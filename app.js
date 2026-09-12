const docs = [
  {
    id: 'full-catalog',
    title: 'Full Catalog',
    file: 'full_catalog.md',
    category: 'full-catalog',
    content: ''
  }
];

const state = {
  activeDocId: 'full-catalog',
  filter: 'catalog', // 'catalog' or 'full-catalog'
  query: '',
  activePreset: 'all',
  catalogData: [],
  catalogFilters: {
    store: 'all',
    brand: 'all',
    price: 0,
    cpuGen: 'all',
    ram: 0,
    storage: 0,
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
const priceFilter = typeof document !== 'undefined' ? document.getElementById('priceFilter') : null;
const cpuGenFilter = typeof document !== 'undefined' ? document.getElementById('cpuGenFilter') : null;
const ramFilter = typeof document !== 'undefined' ? document.getElementById('ramFilter') : null;
const storageFilter = typeof document !== 'undefined' ? document.getElementById('storageFilter') : null;
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

function formatCpuHtml(cpuStr) {
  if (!cpuStr) return 'N/A';
  const genMatch = String(cpuStr).match(/^(.*?)\s*\(([^)]+Gen)\)$/i);
  if (genMatch) {
    const mainCpu = genMatch[1].trim();
    const genTag = genMatch[2].trim();
    return `<span class="cpu-name">${escapeHtml(mainCpu)}</span><span class="cpu-gen-badge">${escapeHtml(genTag)}</span>`;
  }
  return escapeHtml(cpuStr);
}

function getCpuGenRank(cpuStr) {
  const cpuL = String(cpuStr || '').toLowerCase();
  const m = cpuL.match(/(\d+)th\s*gen/i);
  if (m) return parseInt(m[1], 10);
  if (cpuL.includes('ultra') || cpuL.includes('14th')) return 14;
  if (cpuL.includes('13th')) return 13;
  if (cpuL.includes('12th')) return 12;
  if (cpuL.includes('11th')) return 11;
  if (cpuL.includes('10th')) return 10;
  if (cpuL.includes('9th')) return 9;
  if (cpuL.includes('8th')) return 8;
  if (cpuL.includes('7th')) return 7;
  if (cpuL.includes('6th')) return 6;
  if (cpuL.includes('5th')) return 5;
  if (cpuL.includes('4th')) return 4;
  if (cpuL.includes('m1') || cpuL.includes('m2') || cpuL.includes('m3') || cpuL.includes('apple')) return 11;
  if (cpuL.includes('ryzen') || cpuL.includes('amd')) return 11;
  return 0;
}

function matchesCpuGen(cpuStr, cpuGen) {
  if (!cpuGen || cpuGen === 'all') return true;
  const cpuL = String(cpuStr || '').toLowerCase();
  const rank = getCpuGenRank(cpuL);

  // Range options (& Up / & Down)
  if (cpuGen.endsWith('-up')) {
    const minGen = parseInt(cpuGen, 10);
    return rank >= minGen;
  }
  if (cpuGen.endsWith('-down')) {
    const maxGen = parseInt(cpuGen, 10);
    return rank > 0 && rank <= maxGen && !cpuL.includes('apple') && !cpuL.includes('amd');
  }

  // Exact family / brand options
  if (cpuGen === '12+') {
    return cpuL.includes('12th') || cpuL.includes('13th') || cpuL.includes('14th') || cpuL.includes('ultra');
  }
  if (cpuGen === '11') {
    return cpuL.includes('11th');
  }
  if (cpuGen === '10') {
    return cpuL.includes('10th');
  }
  if (cpuGen === '8') {
    return cpuL.includes('8th') || cpuL.includes('9th');
  }
  if (cpuGen === 'older') {
    return (
      cpuL.includes('7th') ||
      cpuL.includes('6th') ||
      cpuL.includes('5th') ||
      cpuL.includes('4th') ||
      cpuL.includes('3rd') ||
      cpuL.includes('2nd')
    );
  }
  if (cpuGen === 'apple') {
    return cpuL.includes('m1') || cpuL.includes('m2') || cpuL.includes('m3') || cpuL.includes('apple');
  }
  if (cpuGen === 'amd') {
    return cpuL.includes('ryzen') || cpuL.includes('amd');
  }
  return true;
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

function renderCatalogToc() {
  if (!tabList || !documentContent) return;
  const headings = documentContent.querySelectorAll('h2');
  if (headings.length === 0) {
    tabList.innerHTML = '<div class="empty-state">No sections found.</div>';
    return;
  }

  let html = '';
  headings.forEach((h, idx) => {
    const sectionId = `store-section-${idx}`;
    h.id = sectionId;
    const rawText = h.textContent.replace(/^##\s*/, '').trim();
    const cleanTitle = rawText.split('—')[0].trim();
    html += `
      <button
        type="button"
        class="tab-button"
        data-target="${sectionId}"
        role="tab"
      >
        <span>${escapeHtml(cleanTitle)}</span>
      </button>
    `;
  });

  tabList.innerHTML = html;
  tabList.querySelectorAll('.tab-button').forEach((btn) => {
    btn.addEventListener('click', () => {
      tabList.querySelectorAll('.tab-button').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      const targetEl = document.getElementById(btn.dataset.target);
      if (targetEl) {
        targetEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });
}

function applyDocSearchFilter() {
  if (!documentContent) return;
  const q = state.query.toLowerCase();
  const rows = documentContent.querySelectorAll('table tr');
  rows.forEach((row) => {
    if (row.querySelector('th')) return;
    if (!q) {
      row.style.display = '';
    } else {
      row.style.display = row.textContent.toLowerCase().includes(q) ? '' : 'none';
    }
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

  const doc = docs[0];
  if (!doc) return;

  setStatus(`Loading ${doc.title}…`);

  if (!doc.content) {
    documentContent.innerHTML = '<div class="empty-state">Loading full catalog…</div>';
    try {
      const response = await fetch(`./${doc.file}`, { cache: 'no-store' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      doc.content = await response.text();
    } catch (error) {
      documentContent.innerHTML = `
        <div class="empty-state">
          <div>
            <h3>Unable to load full catalog.</h3>
            <p>${escapeHtml(error.message)}</p>
          </div>
        </div>
      `;
      setStatus('Could not load full catalog.', 'error');
      return;
    }
  }

  const sanitized = sanitizeMarkdown(doc.content);
  const rendered = DOMPurify.sanitize(marked.parse(sanitized));
  documentContent.innerHTML = rendered;

  renderCatalogToc();
  applyDocSearchFilter();
  setStatus(`${doc.title} loaded`, 'success');
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
  } else if (preset === 'under-2000') {
    state.catalogFilters.price = 2000;
    if (priceFilter) priceFilter.value = '2000';
  } else if (preset === 'ram-32') {
    state.catalogFilters.ram = 32;
    if (ramFilter) ramFilter.value = '32';
  } else if (preset === '2in1') {
    state.catalogFilters.form = '2in1';
    if (formFilter) formFilter.value = '2in1';
  } else if (preset === 'warranty-24') {
    state.catalogFilters.store = 'Ecology Computers';
    if (storeFilter) storeFilter.value = 'Ecology Computers';
  } else if (preset === 'modular') {
    state.catalogFilters.upgradability = 7;
    if (upgradabilityFilter) upgradabilityFilter.value = '7';
  } else if (preset === 'budget') {
    state.catalogFilters.price = 1600;
    if (priceFilter) priceFilter.value = '1600';
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
      price: 0,
      cpuGen: 'all',
      ram: 0,
      storage: 0,
      form: 'all',
      screen: 'all',
      weight: 0,
      battery: 0,
      upgradability: 0,
      sort: 'value-desc'
    };
    if (storeFilter) storeFilter.value = 'all';
    if (brandFilter) brandFilter.value = 'all';
    if (priceFilter) priceFilter.value = '0';
    if (cpuGenFilter) cpuGenFilter.value = 'all';
    if (ramFilter) ramFilter.value = '0';
    if (storageFilter) storageFilter.value = '0';
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
  const { store, brand, price, cpuGen, ram, storage, form, screen, weight, battery, upgradability, sort } = state.catalogFilters;
  const q = state.query.toLowerCase();

  let filtered = state.catalogData.filter((item) => {
    if (store !== 'all' && item.store !== store) return false;
    if (brand !== 'all' && item.brand.toLowerCase() !== brand.toLowerCase()) return false;

    // Price Range (& Down / & Up)
    if (price && price !== '0' && price !== 0) {
      const pVal = item.deal_price_ils || item.price_ils || 0;
      const pStr = String(price);
      if (pStr.endsWith('-up')) {
        const minP = parseFloat(pStr);
        if (pVal < minP) return false;
      } else {
        const maxP = parseFloat(pStr);
        if (maxP > 0 && pVal > maxP) return false;
      }
    }

    if (!matchesCpuGen(item.cpu, cpuGen)) return false;

    // RAM Range (& Up / & Down / Exact)
    if (ram && ram !== '0' && ram !== 0) {
      const rStr = String(ram);
      if (rStr.endsWith('-down')) {
        const maxR = parseFloat(rStr);
        if (item.ram_gb > maxR) return false;
      } else if (rStr.endsWith('-exact')) {
        const exactR = parseFloat(rStr);
        if (item.ram_gb !== exactR) return false;
      } else {
        const minR = parseFloat(rStr);
        if (minR > 0 && item.ram_gb < minR) return false;
      }
    }

    // Storage Range (& Up / & Down / Exact)
    if (storage && storage !== '0' && storage !== 0) {
      const sStr = String(storage);
      if (sStr.endsWith('-down')) {
        const maxS = parseFloat(sStr);
        if (item.storage_gb > (maxS + 30)) return false;
      } else if (sStr.endsWith('-exact')) {
        const exactS = parseFloat(sStr);
        if (Math.abs(item.storage_gb - exactS) > 30) return false;
      } else {
        const minS = parseFloat(sStr);
        if (minS > 0 && item.storage_gb < (minS - 30)) return false;
      }
    }

    // Upgradability (& Up / & Down)
    if (upgradability && upgradability !== '0' && upgradability !== 0) {
      const uStr = String(upgradability);
      if (uStr.endsWith('-down')) {
        const maxU = parseFloat(uStr);
        if (item.upgradability_score > (maxU + 0.5)) return false;
      } else {
        const minU = parseFloat(uStr);
        if (minU > 0 && item.upgradability_score < minU) return false;
      }
    }

    if (form === '2in1' && (!item.is_2in1 && !item.is_touch)) return false;
    if (form === 'clamshell' && (item.is_2in1 || item.is_touch)) return false;

    // Screen Size Range (& Up / & Down / Exact)
    if (screen !== 'all') {
      const scStr = String(screen);
      if (scStr.endsWith('-up')) {
        const minS = parseFloat(scStr);
        if (item.screen_size_in < (minS - 0.15)) return false;
      } else if (scStr.endsWith('-down')) {
        const maxS = parseFloat(scStr);
        if (item.screen_size_in > (maxS + 0.15)) return false;
      } else if (scStr === 'large') {
        if (item.screen_size_in < 15.0) return false;
      } else if (scStr === 'compact') {
        if (item.screen_size_in > 13.6) return false;
      } else {
        const exactS = parseFloat(scStr);
        if (exactS > 0 && Math.abs(item.screen_size_in - exactS) > 0.3) return false;
      }
    }

    // Weight Range (& Down / & Up)
    if (weight && weight !== '0' && weight !== 0) {
      const wStr = String(weight);
      if (wStr.endsWith('-up')) {
        const minW = parseFloat(wStr);
        if (item.weight_kg < (minW - 0.05)) return false;
      } else {
        const maxW = parseFloat(wStr);
        if (maxW > 0 && item.weight_kg > (maxW + 0.05)) return false;
      }
    }

    // Battery Range (& Up / & Down)
    if (battery && battery !== '0' && battery !== 0) {
      const bStr = String(battery);
      if (bStr.endsWith('-down')) {
        const maxB = parseFloat(bStr);
        if (item.battery_wh > maxB) return false;
      } else {
        const minB = parseFloat(bStr);
        if (minB > 0 && item.battery_wh < minB) return false;
      }
    }

    if (q) {
      const touchKeywords = item.is_touch || item.is_2in1 ? 'touch touchscreen טאץ טאצ' : '';
      const formKeywords = item.is_2in1 ? '2in1 2-in-1 convertible 360' : 'clamshell';
      const storageStr = item.storage_gb ? `${item.storage_gb}gb ${item.storage_gb} ssd` : '';
      const searchHaystack = `${item.title} ${item.brand} ${item.store} ${item.cpu} ${item.ram_gb}GB ${storageStr} ${item.screen_size_in}inch ${item.weight_kg}kg ${item.battery_wh}wh ${item.storage_type} ${touchKeywords} ${formKeywords} ${item.warranty_months}months`.toLowerCase();
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
        <button type="button" class="chip-btn ${state.activePreset === 'under-2000' ? 'active' : ''}" data-preset="under-2000">💰 Under 2,000 ₪</button>
        <button type="button" class="chip-btn ${state.activePreset === 'featherlight' ? 'active' : ''}" data-preset="featherlight">🪶 Featherlight (&lt; 1.3kg)</button>
        <button type="button" class="chip-btn ${state.activePreset === 'long-battery' ? 'active' : ''}" data-preset="long-battery">🔋 Long Battery (55Wh+)</button>
        <button type="button" class="chip-btn ${state.activePreset === 'large-screen' ? 'active' : ''}" data-preset="large-screen">🖥️ Large Display (15"+)</button>
        <button type="button" class="chip-btn ${state.activePreset === 'ram-32' ? 'active' : ''}" data-preset="ram-32">⚡ 32GB RAM Deals</button>
        <button type="button" class="chip-btn ${state.activePreset === '2in1' ? 'active' : ''}" data-preset="2in1">🔄 2-in-1 / Touch</button>
        <button type="button" class="chip-btn ${state.activePreset === 'warranty-24' ? 'active' : ''}" data-preset="warranty-24">🛡️ 2-Year Warranty</button>
        <button type="button" class="chip-btn ${state.activePreset === 'modular' ? 'active' : ''}" data-preset="modular">🟢 Modular (7+)</button>
      </div>
    </div>
  `;

  if (filtered.length === 0) {
    catalogContent.innerHTML = `
      ${chipsHtml}
      <div class="empty-state">
        <div style="font-size: 2.2rem; margin-bottom: 8px;">🔍</div>
        <h3>No laptops match your selected filters.</h3>
        <p>Try widening your search terms, raising the budget, or clearing filter criteria.</p>
        <button type="button" class="filter-btn active reset-empty-btn" style="margin-top: 14px; display: inline-flex;">🔄 Reset All Filters</button>
      </div>
    `;
    bindChipButtons();
    const resetBtn = catalogContent.querySelector('.reset-empty-btn');
    if (resetBtn) {
      resetBtn.addEventListener('click', () => setQuickPreset('all'));
    }
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
                ${laptop.warranty_months >= 24 ? '<span class="badge-warranty-24m">🛡️ 2-Yr Warranty</span>' : ''}
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
              <span class="spec-value">${formatCpuHtml(laptop.cpu)}</span>
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
      <a href="./scraped_laptops.csv" download="refurbished_laptops.csv" class="export-csv-btn">⬇️ Download CSV</a>
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
        applyDocSearchFilter();
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

  if (priceFilter) {
    priceFilter.addEventListener('change', (e) => {
      state.catalogFilters.price = e.target.value;
      state.activePreset = '';
      renderCatalog();
    });
  }

  if (cpuGenFilter) {
    cpuGenFilter.addEventListener('change', (e) => {
      state.catalogFilters.cpuGen = e.target.value;
      state.activePreset = '';
      renderCatalog();
    });
  }

  if (ramFilter) {
    ramFilter.addEventListener('change', (e) => {
      state.catalogFilters.ram = e.target.value;
      state.activePreset = '';
      renderCatalog();
    });
  }

  if (storageFilter) {
    storageFilter.addEventListener('change', (e) => {
      state.catalogFilters.storage = e.target.value;
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
      state.catalogFilters.weight = e.target.value;
      state.activePreset = '';
      renderCatalog();
    });
  }

  if (batteryFilter) {
    batteryFilter.addEventListener('change', (e) => {
      state.catalogFilters.battery = e.target.value;
      state.activePreset = '';
      renderCatalog();
    });
  }

  if (upgradabilityFilter) {
    upgradabilityFilter.addEventListener('change', (e) => {
      state.catalogFilters.upgradability = e.target.value;
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
  module.exports = { escapeHtml, calculateValueScore, formatCpuHtml, matchesCpuGen, getCpuGenRank };
}
