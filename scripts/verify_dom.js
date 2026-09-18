// 用 jsdom 真实加载页面，验证静态渲染与各项交互（无脚本也应完整可读）
const fs = require('fs');
const path = require('path');
const { JSDOM, VirtualConsole } = require(
  path.join('C:/Users/hp/.workbuddy/binaries/node/workspace/node_modules/jsdom'));

const file = process.argv[2] ||
  'C:/Users/hp/WorkBuddy/2026-09-18-09-00-11/weekly-site/科技爱好者集锦.html';
const html = fs.readFileSync(file, 'utf8');

const errors = [];
const vc = new VirtualConsole();
vc.on('jsdomError', e => errors.push(e.message));
vc.on('error', (...a) => errors.push(String(a[0])));

const dom = new JSDOM(html, { runScripts: 'dangerously', virtualConsole: vc });
const { document } = dom.window;

const Q = s => document.querySelectorAll(s);
const visible = s => Array.from(Q(s)).filter(e => e.style.display !== 'none').length;
const res = () => document.querySelector('#res').textContent.trim();
let fail = 0;
function check(name, got, want) {
  const ok = String(got) === String(want);
  if (!ok) fail++;
  console.log(`${ok ? '✓' : '✗'} ${name}: ${got}${ok ? '' : `（应为 ${want}）`}`);
}

console.log('— 静态渲染 —');
check('正文卡片', Q('#listTheme .card').length, 189);
check('分组', Q('#listTheme .group').length, 12);
check('统计项已移除', Q('.stat').length, 0);
check('主题速览已移除', Q('.tcard').length, 0);
check('主题芯片已移除', Q('.chip').length, 0);

console.log('\n— 交互 —');
check('初始可见', visible('#listTheme .card'), 189);
const sec = Array.from(Q('#segSec button')).find(b => b.getAttribute('data-v') === '言论');
sec.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }));
check('切到言论', visible('#listTheme .card'), 152);
const all = Array.from(Q('#segSec button')).find(b => b.getAttribute('data-v') === 'all');
all.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }));
check('切回全部', visible('#listTheme .card'), 189);

const q = document.querySelector('#q');
q.value = '晋升';
q.dispatchEvent(new dom.window.Event('input', { bubbles: true }));
const n1 = visible('#listTheme .card');
check('搜索命中', n1 > 0 && n1 < 189, 'true');
console.log('  「晋升」命中', n1, '条 |', res());
q.value = '';
q.dispatchEvent(new dom.window.Event('input', { bubbles: true }));

const iss = Array.from(Q('#segView button')).find(b => b.getAttribute('data-v') === 'issue');
iss.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }));
check('期号视图卡片', Q('#listIssue .card').length, 189);
check('期号视图分组', Q('#listIssue .group').length, 34);

console.log('\nJS 运行时错误:', errors.length ? errors : '无');
console.log(fail === 0 ? '\n全部通过' : `\n失败 ${fail} 项`);
process.exit(fail === 0 ? 0 : 1);
