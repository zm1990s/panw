const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'zt-architect.html'), 'utf8');
function literal(name, end) {
  const start = source.indexOf(`const ${name} = `);
  if (start < 0) throw new Error(`Missing ${name}`);
  const text = source.slice(start + `const ${name} = `.length, source.indexOf(end, start));
  return vm.runInNewContext(`(${text.trim().replace(/;$/, '')})`, {}, { timeout: 1000 });
}
const mods = literal('MODS', '\n\nPRESETS.find');
const groups = literal('GROUPS', '\n\n// col:');
const pills = literal('VERIF_PILLS', '\n\nconst I18N');
const catalog = [...Object.entries(mods).map(([id, m]) => ({ id, label:m.label, group:groups.find(g => g.mods.includes(id))?.label || m.sec, items:m.items })), ...pills.map(p => ({id:p.id,label:p.label,group:'持续验证',items:[p.tip.zh]}))];
const lucide = require(process.env.LUCIDE_PATH || 'lucide');
const names = ['Network','Server','Container','Component','Router','BrickWallFire','Monitor','Shield','KeyRound','Cloud','Bot','Database','Plus','Minus','Maximize','MousePointer2','Hand','Cable','Undo2','Redo2','Save','FolderOpen','Download','Image','Search','X','Trash2','Copy','ChevronRight','PanelRightClose','List','LayoutGrid','Check','CheckCheck','Circle','Activity','HardDrive','Cpu','MemoryStick','Settings2','GitBranch','LockKeyhole','ExternalLink','Filter','ArrowRight','RotateCcw','FileJson','FileCode','Map','CheckSquare'];
names.push('Move','Magnet','Pencil','SquarePlus');
const icons = Object.fromEntries(names.map(n => [n,lucide.icons[n]]));
const safe = value => JSON.stringify(value).replace(/</g,'\\u003c');
let html = fs.readFileSync(path.join(__dirname,'template.html'),'utf8');
html = html.replace('/* STYLES */', () => fs.readFileSync(path.join(__dirname,'style.css'),'utf8'))
  .replace('/* CATALOG */', () => `/*\n${fs.readFileSync(path.join(__dirname,'LUCIDE-LICENSE'),'utf8')}\n*/\nconst CATALOG = ${safe(catalog)}; const ICONS = ${safe(icons)};`)
  .replace('/* SEED */', () => fs.readFileSync(path.join(__dirname,'seed.js'),'utf8'))
  .replace('/* FILE_SAVE */', () => fs.readFileSync(path.join(__dirname,'file-save.js'),'utf8'))
  .replace('/* APP */', () => fs.readFileSync(path.join(__dirname,'app.js'),'utf8'));
const outputPath = path.join(root,'homelab.html');
if (fs.existsSync(outputPath)) {
  const saved = fs.readFileSync(outputPath,'utf8').match(/<script id="saved-project" type="application\/json">([\s\S]*?)<\/script>/);
  if (saved && JSON.parse(saved[1])) html = html.replace('<script id="saved-project" type="application/json">null</script>', () => `<script id="saved-project" type="application/json">${safe(JSON.parse(saved[1]))}</script>`);
}
fs.writeFileSync(outputPath,html);
console.log(`Built homelab.html with ${catalog.length} architecture capabilities.`);
