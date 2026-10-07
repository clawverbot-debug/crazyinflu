// The public data and media remain on Netlify; only the interface is built here.
import { mkdir, readFile, writeFile } from 'node:fs/promises';

const source = await readFile(new URL('./index.html', import.meta.url), 'utf8');
const output = new URL('./vercel-dist/', import.meta.url);
await mkdir(output, { recursive: true });
await writeFile(new URL('index.html', output), `<!doctype html>\n<html lang="fr">\n${source}\n</html>\n`);
console.log('Built Character Lab interface in dashboard/vercel-dist/index.html');
