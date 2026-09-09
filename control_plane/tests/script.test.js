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

test('updateChatDrawerPosition moves drawer slightly left when node properties open, docking next to sidebar, and back to right when closed', () => {
  const drawerClasses = new Set();
  const drawerStyle = { right: '', left: '', display: 'flex' };
  const sidebarStyle = { display: 'none' };
  const sidebarEl = { style: sidebarStyle, offsetWidth: 400 };
  const drawerEl = {
    style: drawerStyle,
    classList: {
      add: (cls) => drawerClasses.add(cls),
      remove: (cls) => drawerClasses.delete(cls),
      contains: (cls) => drawerClasses.has(cls)
    }
  };

  global.document = {
    getElementById: (id) => {
      if (id === 'chat-drawer') return drawerEl;
      if (id === 'sidebar') return sidebarEl;
      return null;
    }
  };

  // 1. Sidebar is closed -> positioned on right edge (right: 16px, left: auto)
  script.updateChatDrawerPosition();
  assert.equal(drawerStyle.right, '16px');
  assert.equal(drawerStyle.left, 'auto');

  // 2. Node properties sidebar is opened -> moves slightly to left to dock adjacent to sidebar (right: 416px, left: auto)
  sidebarStyle.display = 'flex';
  script.updateChatDrawerPosition();
  assert.equal(drawerStyle.right, '416px');
  assert.equal(drawerStyle.left, 'auto');
  assert.equal(drawerClasses.has('dock-left'), false);
  assert.equal(drawerClasses.has('dock-right'), false);

  // 3. Node properties sidebar is closed -> moves smoothly back to right edge (right: 16px, left: auto)
  sidebarStyle.display = 'none';
  script.updateChatDrawerPosition();
  assert.equal(drawerStyle.right, '16px');
  assert.equal(drawerStyle.left, 'auto');
});

