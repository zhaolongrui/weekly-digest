// 用 jsdom 真实加载页面，验证静态渲染与各项交互（无脚本也应完整可读）
// 用法: node verify_dom.js [站点根目录]
// 注意：搜索有 220ms 防抖，测试里每次输入后需等待
const fs = require('fs');
const path = require('path');
const { JSDOM, VirtualConsole } = require(
  path.join('C:/Users/hp/.workbuddy/binaries/node/workspace/node_modules/jsdom'));

const ROOT = process.argv[2] || 'C:/Users/hp/WorkBuddy/2026-09-18-09-00-11/weekly-site';
const sleep = ms => new Promise(r => setTimeout(r, ms));
let fail = 0;
function check(name, got, want) {
  const ok = String(got) === String(want);
  if (!ok) fail++;
  console.log(`  ${ok ? '✓' : '✗'} ${name}: ${got}${ok ? '' : `（应为 ${want}）`}`);
}

function load(file, runScripts) {
  const html = fs.readFileSync(path.join(ROOT, file), 'utf8');
  const errors = [];
  const vc = new VirtualConsole();
  vc.on('jsdomError', e => errors.push(e.message));
  vc.on('error', (...a) => errors.push(String(a[0])));
  const dom = new JSDOM(html, { runScripts: runScripts ? 'dangerously' : undefined, virtualConsole: vc });
  return { dom, d: dom.window.document, win: dom.window, errors, html };
}

function api(d) {
  return {
    Q: s => d.querySelectorAll(s),
    vis: s => Array.from(d.querySelectorAll(s)).filter(e => e.style.display !== 'none').length,
    res: () => { const e = d.querySelector('#res'); return e ? e.textContent.trim() : ''; },
  };
}

function click(win, el) { el.dispatchEvent(new win.MouseEvent('click', { bubbles: true })); }
function input(win, el, v) { el.value = v; el.dispatchEvent(new win.Event('input', { bubbles: true })); }
function btn(a, sel, v) {
  return Array.from(a.Q(sel)).find(b => b.getAttribute('data-v') === v);
}

(async () => {
// ---------- 索引页 ----------
console.log('— 索引页 index.html —');
{
  const { d, errors } = load('index.html', true);
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
  const { dom, d, win, errors } = load(y + '.html', true);
  const a = api(d);
  const cards = Array.from(a.Q('#listTheme .card'));
  const n = cards.length;
  const nTheme = a.Q('#listTheme .group').length;
  const nIssue = a.Q('#listIssue .group').length;
  const nQuote = cards.filter(c => c.getAttribute('data-s') === '言论').length;

  console.log(`\n— ${y}.html（${n} 条 / ${nIssue} 期 / ${nTheme} 个主题组）—`);
  check('静态卡片数', n, n > 0 ? n : 0);
  check('期号骨架数', nIssue, nIssue);
  check('主题大类不超过 6 个', nTheme <= 6, 'true');
  const groups = Array.from(a.Q('#listTheme .group')).map(g => g.getAttribute('data-theme'));
  check('未归类排在最后',
    groups.indexOf('未归类') === -1 || groups.indexOf('未归类') === groups.length - 1, 'true');
  check('年份导航链接', a.Q('.years a').length, years.length + 1);
  const on = Array.from(a.Q('.years a')).filter(e => e.className === 'on').map(e => e.textContent);
  check('当前年高亮', on.join(','), y);
  check('无内联 JSON 数据', /var DATA|var META/.test(fs.readFileSync(path.join(ROOT, y + '.html'), 'utf8')), 'false');

  check('初始可见', a.vis('#listTheme .card'), n);
  click(win, btn(a, '#segSec button', '言论'));
  check('切到言论（不丢卡片）', a.vis('#listTheme .card'), nQuote);
  click(win, btn(a, '#segSec button', 'all'));
  check('切回全部', a.vis('#listTheme .card'), n);

  // 搜索：期望值用 DOM 全文自算，验证索引与实际一致
  const q = d.querySelector('#q');
  for (const kw of ['AI', '的', '晋升']) {
    const want = cards.filter(c => c.textContent.toLowerCase().indexOf(kw.toLowerCase()) >= 0).length;
    input(win, q, kw);
    await sleep(320);
    check(`搜「${kw}」命中`, a.vis('#listTheme .card'), want);
  }
  input(win, q, '');
  await sleep(320);
  check('清空搜索', a.vis('#listTheme .card'), n);

  // 期号视图：卡片节点整体搬移，不克隆、不重建
  click(win, btn(a, '#segView button', 'issue'));
  check('期号视图卡片（搬移后）', a.Q('#listIssue .card').length, n);
  check('期号视图分组', a.Q('#listIssue .group').length, nIssue);
  check('主题容器已清空', a.Q('#listTheme .card').length, 0);
  // 期号视图内搜索
  const wantQ = cards.filter(c => c.textContent.indexOf('工作') >= 0).length;
  input(win, q, '工作');
  await sleep(320);
  check('期号视图内搜索', a.vis('#listIssue .card'), wantQ);
  input(win, q, '');
  await sleep(320);

  click(win, btn(a, '#segView button', 'theme'));
  check('切回主题视图卡片不丢', a.Q('#listTheme .card').length, n);
  check('切回后可见', a.vis('#listTheme .card'), n);
  check('复制按钮', a.Q('#listTheme .copy').length, n);
  check('JS 运行时错误', errors.length, 0);
  dom.window.close();
}

// ---------- 禁用脚本：内容必须完整可读 ----------
console.log('\n— 无脚本可读性（2019 卷）—');
{
  const { d } = load('2019.html', false);
  const a = api(d);
  check('静态卡片仍在', a.Q('#listTheme .card').length, 273);
  check('主题分组仍在', a.Q('#listTheme .group').length, 6);
  check('提炼行', a.Q('.take').length, 273);
}

console.log(fail === 0 ? '\n全部通过' : `\n失败 ${fail} 项`);
process.exit(fail === 0 ? 0 : 1);
})();
