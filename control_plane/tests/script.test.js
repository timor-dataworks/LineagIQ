const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const scriptPath = path.join(__dirname, '../src/static/script.js');
const script = require(scriptPath);

test('escapeHtml correctly escapes special HTML characters', () => {
  assert.equal(script.escapeHtml('<div>Hello & "World"</div>'), '&lt;div&gt;Hello &amp; "World"&lt;/div&gt;');
  assert.equal(script.escapeHtml('<script>alert("xss")</script>'), '&lt;script&gt;alert("xss")&lt;/script&gt;');
  assert.equal(script.escapeHtml(''), '');
  assert.equal(script.escapeHtml(null), '');
});

test('formatMarkdown renders bold, code, and line breaks properly', () => {
  const raw = "**bold text** and `code block` with\nnew line";
  const expected = "<strong>bold text</strong> and <code style='background: rgba(2, 6, 23, 0.6); color: #38bdf8; padding: 2px 6px; border-radius: 4px;'>code block</code> with<br>new line";
  assert.equal(script.formatMarkdown(raw), expected);
  assert.equal(script.formatMarkdown(''), '');
  assert.equal(script.formatMarkdown(null), '');
});

test('typeColors contains accurate color configuration for knowledge graph node types', () => {
  assert.ok(script.typeColors.Dataset);
  assert.equal(script.typeColors.Dataset.background, '#0284c7');
  assert.ok(script.typeColors.Column);
  assert.equal(script.typeColors.Column.background, '#7c3aed');
  assert.ok(script.typeColors.Pipeline);
  assert.equal(script.typeColors.Pipeline.background, '#d97706');
});

test('switchDiffTab toggles active tab classes and display styles', () => {
  const tabs = ['added', 'removed', 'modified', 'edges', 'prompt'];
  const elements = {};

  tabs.forEach(t => {
    const btnClassList = new Set();
    const contentStyle = { display: '' };
    elements[`tab-btn-${t}`] = {
      classList: {
        add: (c) => btnClassList.add(c),
        remove: (c) => btnClassList.delete(c),
        contains: (c) => btnClassList.has(c)
      }
    };
    elements[`diff-tab-${t}`] = { style: contentStyle };
  });

  global.document = {
    getElementById: (id) => elements[id] || null
  };

  script.switchDiffTab('added');

  assert.ok(elements['tab-btn-added'].classList.contains('active'));
  assert.equal(elements['diff-tab-added'].style.display, 'flex');
  assert.ok(!elements['tab-btn-removed'].classList.contains('active'));
  assert.equal(elements['diff-tab-removed'].style.display, 'none');

  script.switchDiffTab('prompt');

  assert.ok(!elements['tab-btn-added'].classList.contains('active'));
  assert.equal(elements['diff-tab-added'].style.display, 'none');
  assert.ok(elements['tab-btn-prompt'].classList.contains('active'));
  assert.equal(elements['diff-tab-prompt'].style.display, 'flex');
});
