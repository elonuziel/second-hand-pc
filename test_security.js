const assert = require('assert');
const { escapeHtml } = require('./app.js');

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

console.log('All security tests passed successfully!');
