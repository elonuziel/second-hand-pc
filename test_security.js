const assert = require('assert');
const { escapeHtml, calculateValueScore, formatCpuHtml, matchesCpuGen } = require('./app.js');

console.log('Running security tests for escapeHtml...');

// Test 1: Basic HTML character escaping
const payload1 = '<script>alert("xss")</script>';
const expected1 = '&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;';
assert.strictEqual(escapeHtml(payload1), expected1, 'Failed to escape basic script tags');

// Test 2: Attribute injection with single/double quotes and ampersands
const payload2 = '"><img src=x onerror=alert(1)>';
const expected2 = '&quot;&gt;&lt;img src=x onerror=alert(1)&gt;';
assert.strictEqual(escapeHtml(payload2), expected2, 'Failed to escape attribute injection payload');

// Test 3: Null or undefined inputs
assert.strictEqual(escapeHtml(null), '', 'Failed on null input');
assert.strictEqual(escapeHtml(undefined), '', 'Failed on undefined input');

// Test 4: Safe string unchanged
const safeString = 'Project overview 123';
assert.strictEqual(escapeHtml(safeString), safeString, 'Modified safe string');

// Test 5: Value score calculation tests
console.log('Running tests for calculateValueScore...');
const budgetHighSpec = {
  deal_price_ils: 1800,
  ram_gb: 32,
  storage_gb: 1000,
  upgradability_score: 9.0,
  cpu: 'Core i7 (11th Gen)'
};
const score1 = calculateValueScore(budgetHighSpec);
assert.ok(score1 >= 8.5 && score1 <= 9.9, `Expected top score for high spec deal, got ${score1}`);

const overPricedLowSpec = {
  deal_price_ils: 3500,
  ram_gb: 8,
  storage_gb: 256,
  upgradability_score: 4.0,
  cpu: 'Core i5 (8th Gen)'
};
const score2 = calculateValueScore(overPricedLowSpec);
assert.ok(score2 <= 6.5, `Expected low score for overpriced weak spec, got ${score2}`);

// Edge case: invalid/zero price returns baseline
assert.strictEqual(calculateValueScore({ deal_price_ils: 0 }), 5.0);

// Test 6: CPU Generation HTML formatting
console.log('Running tests for formatCpuHtml...');
assert.strictEqual(
  formatCpuHtml('Core i7 (11th Gen)'),
  '<span class="cpu-name">Core i7</span><span class="cpu-gen-badge">11th Gen</span>'
);
assert.strictEqual(
  formatCpuHtml('Core i5 (10th Gen)'),
  '<span class="cpu-name">Core i5</span><span class="cpu-gen-badge">10th Gen</span>'
);
assert.strictEqual(formatCpuHtml('Apple M1'), 'Apple M1');
assert.strictEqual(formatCpuHtml(null), 'N/A');

// Test 7: CPU Gen filtering
console.log('Running tests for matchesCpuGen...');
assert.strictEqual(matchesCpuGen('Core i7 (12th Gen)', '12+'), true);
assert.strictEqual(matchesCpuGen('Core i5 (13th Gen)', '12+'), true);
assert.strictEqual(matchesCpuGen('Core i7 (11th Gen)', '12+'), false);

assert.strictEqual(matchesCpuGen('Core i5 (11th Gen)', '11'), true);
assert.strictEqual(matchesCpuGen('Core i5 (10th Gen)', '11'), false);

assert.strictEqual(matchesCpuGen('Core i7 (10th Gen)', '10'), true);
assert.strictEqual(matchesCpuGen('Core i7 (8th Gen)', '10'), false);

assert.strictEqual(matchesCpuGen('Core i5 (8th Gen)', '8'), true);
assert.strictEqual(matchesCpuGen('Core i7 (9th Gen)', '8'), true);
assert.strictEqual(matchesCpuGen('Core i5 (7th Gen)', '8'), false);

assert.strictEqual(matchesCpuGen('Core i5 (7th Gen)', 'older'), true);
assert.strictEqual(matchesCpuGen('Core i5 (4th Gen)', 'older'), true);
assert.strictEqual(matchesCpuGen('Core i5 (8th Gen)', 'older'), false);

assert.strictEqual(matchesCpuGen('Apple M1', 'apple'), true);
assert.strictEqual(matchesCpuGen('Apple M2', 'apple'), true);
assert.strictEqual(matchesCpuGen('Core i7 (11th Gen)', 'apple'), false);

assert.strictEqual(matchesCpuGen('AMD Ryzen 5 PRO', 'amd'), true);
assert.strictEqual(matchesCpuGen('Core i5 (11th Gen)', 'amd'), false);

assert.strictEqual(matchesCpuGen('Core i7 (11th Gen)', 'all'), true);
assert.strictEqual(matchesCpuGen(null, 'all'), true);

// Range tests (& Up / & Down)
assert.strictEqual(matchesCpuGen('Core i7 (13th Gen)', '12-up'), true);
assert.strictEqual(matchesCpuGen('Core i5 (12th Gen)', '12-up'), true);
assert.strictEqual(matchesCpuGen('Core i7 (11th Gen)', '12-up'), false);

assert.strictEqual(matchesCpuGen('Core i5 (13th Gen)', '11-up'), true);
assert.strictEqual(matchesCpuGen('Core i7 (11th Gen)', '11-up'), true);
assert.strictEqual(matchesCpuGen('Core i5 (10th Gen)', '11-up'), false);

assert.strictEqual(matchesCpuGen('Core i7 (11th Gen)', '10-up'), true);
assert.strictEqual(matchesCpuGen('Core i5 (10th Gen)', '10-up'), true);
assert.strictEqual(matchesCpuGen('Core i5 (8th Gen)', '10-up'), false);

assert.strictEqual(matchesCpuGen('Core i5 (8th Gen)', '8-up'), true);
assert.strictEqual(matchesCpuGen('Core i7 (12th Gen)', '8-up'), true);
assert.strictEqual(matchesCpuGen('Core i5 (7th Gen)', '8-up'), false);

assert.strictEqual(matchesCpuGen('Core i5 (8th Gen)', '8-down'), true);
assert.strictEqual(matchesCpuGen('Core i5 (6th Gen)', '8-down'), true);
assert.strictEqual(matchesCpuGen('Core i7 (10th Gen)', '8-down'), false);

assert.strictEqual(matchesCpuGen('Core i5 (10th Gen)', '10-down'), true);
assert.strictEqual(matchesCpuGen('Core i7 (8th Gen)', '10-down'), true);
assert.strictEqual(matchesCpuGen('Core i7 (11th Gen)', '10-down'), false);

assert.strictEqual(matchesCpuGen('Core i5 (11th Gen)', '11-down'), true);
assert.strictEqual(matchesCpuGen('Core i7 (12th Gen)', '11-down'), false);

// Test 8: Filter range logic validation
console.log('Running tests for filter range evaluations...');
// Storage matching logic test
function matchesStorage(storageGb, filterVal) {
  if (!filterVal || filterVal === '0' || filterVal === 0) return true;
  const sStr = String(filterVal);
  if (sStr.endsWith('-down')) {
    const maxS = parseFloat(sStr);
    return storageGb <= (maxS + 30);
  } else if (sStr.endsWith('-exact')) {
    const exactS = parseFloat(sStr);
    return Math.abs(storageGb - exactS) <= 30;
  } else {
    const minS = parseFloat(sStr);
    return minS <= 0 || storageGb >= (minS - 30);
  }
}

assert.strictEqual(matchesStorage(256, '256'), true);
assert.strictEqual(matchesStorage(512, '512'), true);
assert.strictEqual(matchesStorage(256, '512'), false);
assert.strictEqual(matchesStorage(1000, '512'), true); // 1TB matches 512 & up
assert.strictEqual(matchesStorage(256, '256-down'), true);
assert.strictEqual(matchesStorage(512, '256-down'), false);
assert.strictEqual(matchesStorage(240, '256-exact'), true); // 240GB within tolerance of 256
assert.strictEqual(matchesStorage(512, '256-exact'), false);

// RAM matching logic test
function matchesRam(ramGb, filterVal) {
  if (!filterVal || filterVal === '0' || filterVal === 0) return true;
  const rStr = String(filterVal);
  if (rStr.endsWith('-down')) {
    return ramGb <= parseFloat(rStr);
  } else if (rStr.endsWith('-exact')) {
    return ramGb === parseFloat(rStr);
  } else {
    return ramGb >= parseFloat(rStr);
  }
}

assert.strictEqual(matchesRam(16, '16'), true);
assert.strictEqual(matchesRam(32, '16'), true);
assert.strictEqual(matchesRam(8, '16'), false);
assert.strictEqual(matchesRam(8, '8-down'), true);
assert.strictEqual(matchesRam(16, '8-down'), false);
assert.strictEqual(matchesRam(16, '16-exact'), true);
assert.strictEqual(matchesRam(32, '16-exact'), false);

console.log('All tests passed successfully!');
