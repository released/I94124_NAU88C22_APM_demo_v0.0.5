import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const docs = [path.join(root, 'README.md'), ...fs.readdirSync(path.join(root, 'docs'))
  .filter(name => name.endsWith('.md') && !['REVIEW.md', 'LEGACY_CHANNELS.md'].includes(name))
  .map(name => path.join(root, 'docs', name)), path.join(root, 'THIRD_PARTY_NOTICES.md')];
let linkCount = 0;
let graphCount = 0;
const diagramDocs = [];
function anchors(source) {
  const seen = new Map();
  return [...source.matchAll(/^#{1,6}\s+(.+)$/gm)].map(match => {
    const base = match[1].replace(/<[^>]*>/g, '').replace(/[*`_]/g, '').toLowerCase()
      .replace(/[^\p{L}\p{N}\p{M}\s-]/gu, '').replace(/\s/g, '-');
    const count = seen.get(base) || 0;
    seen.set(base, count + 1);
    return count ? base + '-' + count : base;
  });
}
for (const file of docs) {
  const source = fs.readFileSync(file, 'utf8');
  if ([...source.matchAll(/^```/gm)].length % 2) throw new Error('Unclosed fence: ' + file);
  const count = [...source.matchAll(/^```mermaid\s*\r?\n([\s\S]*?)^```\s*$/gm)].length;
  graphCount += count;
  if (count) diagramDocs.push(file);
  const withoutCode = source.replace(/^```[\s\S]*?^```\s*$/gm, '');
  for (const match of withoutCode.matchAll(/\[[^\]\r\n]*\]\(([^)\r\n]+)\)/g)) {
    let target = match[1].trim().replace(/^<|>$/g, '');
    if (/^(https?:|mailto:)/i.test(target)) continue;
    const [relative, fragment] = target.split('#');
    target = decodeURIComponent(relative);
    const full = target ? path.resolve(path.dirname(file), target) : file;
    if (!full.startsWith(root + path.sep) || !fs.existsSync(full)) {
      throw new Error('Invalid local link in ' + path.relative(root, file) + ': ' + target);
    }
    const ignored = spawnSync('git', ['check-ignore', '--quiet', '--', full], { cwd: root });
    if (ignored.status === 0) throw new Error('Public link points to an ignored file: ' + target);
    if (fragment && !anchors(fs.readFileSync(full, 'utf8')).includes(decodeURIComponent(fragment))) {
      throw new Error('Invalid local anchor: ' + match[1]);
    }
    linkCount++;
  }
}
console.log(JSON.stringify({ markdownFiles: docs.length, localLinks: linkCount, mermaidGraphs: graphCount }));
if (graphCount < 1) throw new Error('No Mermaid diagrams found');
const arg = process.argv.indexOf('--mermaid-cli');
if (arg !== -1) {
  const cli = process.argv[arg + 1];
  if (!cli || !fs.existsSync(cli)) throw new Error('Provide an installed mermaid-cli src/cli.js path');
  const output = path.join(root, 'verification', 'docs_review', 'run-' + Date.now());
  fs.mkdirSync(output, { recursive: true });
  for (const file of diagramDocs) {
    const result = spawnSync(process.execPath, [
      cli, '-i', file, '-o', path.join(output, path.basename(file, '.md') + '.png'),
      '-s', '1.5', '-j', '2', '-q'
    ], { encoding: 'utf8', windowsHide: true });
    if (result.stdout) process.stdout.write(result.stdout);
    if (result.stderr) process.stderr.write(result.stderr);
    if (result.status !== 0) throw new Error('Mermaid rendering failed with status ' + result.status);
  }
  const pngs = fs.readdirSync(output).filter(name => name.endsWith('.png'));
  if (pngs.length !== graphCount) throw new Error('Rendered graph count does not match source');
  console.log(JSON.stringify({ renderedPNG: pngs.length, output }));
}
