import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const rootDir = dirname(dirname(fileURLToPath(import.meta.url)));
const newsPagesPath = join(rootDir, "lib", "newsPages.js");
const renderersDir = join(rootDir, "app", "news", "[slug]", "renderers");
const indexPath = join(renderersDir, "index.js");
const legacyPath = join(renderersDir, "legacyRenderers.js");

const newsPagesSource = readFileSync(newsPagesPath, "utf8");
const indexSource = readFileSync(indexPath, "utf8");
const legacySource = existsSync(legacyPath) ? readFileSync(legacyPath, "utf8") : "";
const slugs = [...newsPagesSource.matchAll(/slug:\s*"([^"]+)"/g)].map((match) => match[1]);
const errors = [];

for (const slug of slugs) {
  const rendererPath = join(renderersDir, `${slug}.js`);
  if (!existsSync(rendererPath)) {
    errors.push(`Missing renderer module for news slug: ${slug}`);
    continue;
  }
  const rendererSource = readFileSync(rendererPath, "utf8");
  if (!indexSource.includes(`"${slug}"`) && !indexSource.includes(`${slug}:`)) {
    errors.push(`Renderer index does not register news slug: ${slug}`);
  }
  if (!rendererSource.includes("export async function render(searchParams)")) {
    errors.push(`Renderer module does not own its render implementation: ${slug}`);
  }
  if (rendererSource.includes("./legacyRenderers")) {
    errors.push(`Renderer still re-exports from legacyRenderers: ${slug}`);
  }
}

if (!indexSource.includes("return null;")) {
  errors.push("renderNewsPageBody() must return null for unknown slugs.");
}

if (legacySource.includes("renderPageBody")) {
  errors.push("legacyRenderers.js still contains renderPageBody.");
}

if (existsSync(legacyPath)) {
  errors.push("legacyRenderers.js should be deleted after renderer extraction.");
}

if (errors.length > 0) {
  console.error(errors.join("\n"));
  process.exit(1);
}

console.log(`Checked ${slugs.length} news renderer modules.`);
