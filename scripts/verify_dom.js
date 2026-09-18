// 用 jsdom 真实加载页面，验证静态渲染与各项交互（无脚本也应完整可读）
// 用法: node verify_dom.js [站点根目录]
const fs = require('fs');
const path = require('path');
const { JSDOM, VirtualConsole } = require(
  path.join('C:/Users/hp/.workbuddy/binaries/node/workspace/node_modules/jsdom'));

const ROOT = process.argv[2] || 'C:/Users/hp/WorkBuddy/2026-09-18-09-00-11/weekly-site';
let fail = 0;
function check(name, got, want) {
  const ok = String(got) === String(want);
  if (!ok) fail++;
  console.log(`  ${ok ? '✓' : '✗'} ${name}: ${got}${ok ? '' : `（应为 ${want}）`}`);
}

function load(file) {
  const html = fs.readFileSync(path.join(ROOT, file), 'utf8');
  const errors = [];
  const vc = new VirtualConsole();
  vc.on('jsdomError', e => errors.push(e.message));
  vc.on('error', (...a) => errors.push(String(a[0])));
  const dom = new JSDOM(html, { runScripts: 'dangerously', virtualConsole: vc });
  return { dom, d: dom.window.document, win: dom.window, errors, html };
}

function api(d) {
  return {
    Q: s => d.querySelectorAll(s),
    vis: s => Array.from(d.querySelectorAll(s)).filter(e => e.style.display !== 'none').length,
    res: () => { const e = d.querySelector('#res'); return e ? e.textContent.trim() : ''; },
  };
}

// 从 start 处的大括号开始，按括号深度切出完整 JSON（字符串内的括号不计）
function scanJson(s, start) {
  let i = s.indexOf('{', start), depth = 0, str = false, esc = false;
  for (; i < s.length; i++) {
    const c = s[i];
    if (str) {
      if (esc) esc = false; else if (c === '\\') esc = true; else if (c === '"') str = false;
      continue;
    }
    if (c === '"') str = true;
    else if (c === '{') depth++;
    else if (c === '}') { depth--; if (depth === 0) return s.slice(s.indexOf('{', start), i + 1); }
  }
  throw new Error('JSON 未闭合');
}

function click(win, el) { el.dispatchEvent(new win.MouseEvent('click', { bubbles: true })); }
function input(win, el, v) { el.value = v; el.dispatchEvent(new win.Event('input', { bubbles: true })); }
function btn(a, sel, v) {
  return Array.from(a.Q(sel)).find(b => b.getAttribute('data-v') === v);
}

// ---------- 索引页 ----------
console.log('— 索引页 index.html —');
{
  const { d, errors } = load('index.html');
  const a = api(d);
  check('年份分卷入口', a.Q('.vol').length, 9);
  check('最近收录卡片', a.Q('#recent .card').length, 12);
  check('已移除统计/速览/芯片', a.Q('.stat').length + a.Q('.tcard').length + a.Q('.chip').length, 0);
  const hrefs = Array.from(a.Q('.vol')).map(e => e.getAttribute('href'));
  check('分卷链接齐全', hrefs.every(h => /^\d{4}\.html$/.test(h)), 'true');
  const missing = hrefs.filter(h => !fs.existsSync(path.join(ROOT, h)));
  check('分卷文件均存在', missing.length ? missing.join(',') : 0, 0);
  check('JS 运行时错误', errors.length, 0);
}

// ---------- 分卷页 ----------
const years = fs.readdirSync(ROOT).filter(f => /^\d{4}\.html$/.test(f)).map(f => f.slice(0, 4)).sort();
for (const y of years) {
  const { dom, d, win, errors, html } = load(y + '.html');
  const a = api(d);
  const data = JSON.parse(scanJson(html, html.indexOf('var DATA = ') + 'var DATA = '.length));
  const n = data.items.length;
  const themes = new Set(data.items.map(i => i.theme));
  const nIssue = new Set(data.items.map(i => i.issue)).size;

  console.log(`\n— ${y}.html（${n} 条 / ${nIssue} 期）—`);
  check('静态卡片数', a.Q('#listTheme .card').length, n);
  check('主题分组数', a.Q('#listTheme .group').length, themes.size);
  const last = a.Q('#listTheme .group');
  const lastName = last.length ? last[last.length - 1].getAttribute('data-theme') : '';
  const groups = Array.from(a.Q('#listTheme .group')).map(g => g.getAttribute('data-theme'));
  check('未归类排在最后', lastName, groups.indexOf('未归类') === groups.length - 1 || !groups.includes('未归类') ? lastName : 'MISPLACED');
  check('年份导航链接', a.Q('.years a').length, years.length + 1);
  const on = Array.from(a.Q('.years a')).filter(e => e.className === 'on').map(e => e.textContent);
  check('当前年高亮', on.join(','), y);

  check('初始可见', a.vis('#listTheme .card'), n);
  click(win, btn(a, '#segSec button', '言论'));
  const nq = data.items.filter(i => i.section === '言论').length;
  check('切到言论', a.vis('#listTheme .card'), nq);
  click(win, btn(a, '#segSec button', 'all'));
  check('切回全部', a.vis('#listTheme .card'), n);

  const q = d.querySelector('#q');
  input(win, q, 'AI');
  const hit = a.vis('#listTheme .card');
  check('搜索命中合理', hit > 0 && hit <= n, 'true');
  console.log('    搜「AI」命中', hit, '条 |', a.res());
  input(win, q, '');

  click(win, btn(a, '#segView button', 'issue'));
  check('期号视图卡片', a.Q('#listIssue .card').length, n);
  check('期号视图分组', a.Q('#listIssue .group').length, nIssue);
  click(win, btn(a, '#segView button', 'theme'));
  check('切回主题视图', a.vis('#listTheme .card'), n);
  check('复制按钮', a.Q('#listTheme .copy').length, n);
  check('JS 运行时错误', errors.length, 0);
  dom.window.close();
}

console.log(fail === 0 ? '\n全部通过' : `\n失败 ${fail} 项`);
process.exit(fail === 0 ? 0 : 1);
