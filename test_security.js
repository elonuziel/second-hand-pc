const assert = require('assert');
const { escapeHtml, calculateValueScore } = require('./app.js');

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

console.log('All tests passed successfully!');
