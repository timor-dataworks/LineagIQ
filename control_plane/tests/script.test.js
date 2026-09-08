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

test('parseNodeProperties safely parses stringified JSON or returns property object', () => {
  assert.deepEqual(script.parseNodeProperties(null), {});
  assert.deepEqual(script.parseNodeProperties({ properties: { a: 1 } }), { a: 1 });
  assert.deepEqual(script.parseNodeProperties({ properties: '{"b": 2}' }), { b: 2 });
  assert.deepEqual(script.parseNodeProperties({ properties: 'invalid json' }), { raw: 'invalid json' });
});

test('buildColumnToDatasetMap maps column IDs to dataset IDs accurately', () => {
  const nodes = [
    { id: 'db.schema.tbl.col1', type: 'Column', properties: { dataset_id: 'db.schema.tbl' } },
    { id: 'db.schema.tbl.col2', type: 'Column' }
  ];
  const edges = [
    { source_id: 'db.schema.tbl.col2', target_id: 'db.schema.tbl', type: 'BELONGS_TO' }
  ];

  const map = script.buildColumnToDatasetMap(nodes, edges);
  assert.equal(map['db.schema.tbl.col1'], 'db.schema.tbl');
  assert.equal(map['db.schema.tbl.col2'], 'db.schema.tbl');
});

test('computeDeterministicPositions assigns explicit X and Y coordinates in LR mode', () => {
  const nodes = [
    { id: 'raw_table', type: 'Dataset' },
    { id: 'stg_pipe', type: 'Pipeline' },
    { id: 'marts_table', type: 'Dataset' }
  ];
  const edges = [
    { from: 'raw_table', to: 'stg_pipe' },
    { from: 'stg_pipe', to: 'marts_table' }
  ];

  script.computeDeterministicPositions(nodes, edges, true);

  assert.equal(nodes[0].x, 0);
  assert.equal(nodes[1].x, 360);
  assert.equal(nodes[2].x, 720);
  assert.equal(typeof nodes[0].y, 'number');
});

test('updateChatDrawerPosition dynamically positions drawer to right edge or shifts when sidebar is open', () => {
  const drawerStyle = { right: '', left: '', display: 'flex' };
  const sidebarStyle = { display: 'none' };
  const sidebarEl = { style: sidebarStyle, offsetWidth: 400 };
  const drawerEl = { style: drawerStyle };

  global.document = {
    getElementById: (id) => {
      if (id === 'chat-drawer') return drawerEl;
      if (id === 'sidebar') return sidebarEl;
      return null;
    }
  };

  // Sidebar is closed -> docks dynamically to right: 16px
  script.updateChatDrawerPosition();
  assert.equal(drawerStyle.right, '16px');

  // Sidebar is opened -> shifts dynamically to left of sidebar
  sidebarStyle.display = 'flex';
  script.updateChatDrawerPosition();
  assert.equal(drawerStyle.right, '420px');

  // Sidebar closed again -> smoothly docks back to right: 16px
  sidebarStyle.display = 'none';
  script.updateChatDrawerPosition();
  assert.equal(drawerStyle.right, '16px');
});

