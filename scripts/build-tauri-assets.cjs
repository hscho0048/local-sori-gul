// Writes dist/: static files, React UMD builds, and app.jsx precompiled so the webview ships no JSX compiler.
// ponytail: no content-hash cache busting (note-taking's version has it); add it when installers ship upgrades.
const fs = require('node:fs');
const path = require('node:path');
const Babel = require('@babel/standalone');

const root = path.resolve(__dirname, '..');
const dist = path.join(root, 'dist');
fs.rmSync(dist, { recursive: true, force: true });
fs.mkdirSync(path.join(dist, 'vendor'), { recursive: true });
for (const file of ['tokens.css', 'bridge.js']) fs.copyFileSync(path.join(root, file), path.join(dist, file));
fs.cpSync(path.join(root, 'A2Z'), path.join(dist, 'A2Z'), { recursive: true });
for (const [pkg, file] of [['react', 'react.production.min.js'], ['react-dom', 'react-dom.production.min.js']]) {
  fs.copyFileSync(path.join(root, 'node_modules', pkg, 'umd', file), path.join(dist, 'vendor', file));
  fs.copyFileSync(path.join(root, 'node_modules', pkg, 'LICENSE'), path.join(dist, 'vendor', `LICENSE.${pkg}.txt`));
}
const source = fs.readFileSync(path.join(root, 'app.jsx'), 'utf8');
fs.writeFileSync(path.join(dist, 'app.js'), Babel.transform(source, { filename: 'app.jsx', presets: ['react', 'env'] }).code);
const tag = '<script type="text/babel" src="app.jsx"></script>';
const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
if (!html.includes(tag)) throw new Error(`index.html must contain ${tag}`);
fs.writeFileSync(path.join(dist, 'index.html'), html.replace(tag, '<script src="app.js"></script>'));
console.log('dist ready');
