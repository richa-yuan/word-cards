/* Shared loader: find playwright-core without assuming a global install. */
const path = require('path');
const fs = require('fs');

const HERE = __dirname;
const CANDIDATES = [
  'playwright-core',
  path.join(process.cwd(), 'node_modules', 'playwright-core'),
  path.join(HERE, 'node_modules', 'playwright-core'),
  path.join(HERE, '..', 'node_modules', 'playwright-core'),
];

function load() {
  for (const c of CANDIDATES) {
    try { return require(c); } catch (e) { /* next */ }
  }
  const target = path.join(HERE, '..');
  console.log('FAIL  playwright-core is not installed where this script can see it.');
  console.log('      fix:  npm install playwright-core --prefix ' + target);
  console.log('      or:   NODE_PATH=/path/to/node_modules node <this script>');
  if (!fs.existsSync(path.join(target, 'package.json'))) console.log('      (a package.json will be created there)');
  process.exit(1);
}

module.exports = load();
