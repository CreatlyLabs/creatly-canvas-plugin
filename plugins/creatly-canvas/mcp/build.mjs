import { existsSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'
import { build } from 'esbuild'

async function main() {
  const root = dirname(fileURLToPath(import.meta.url))
  const results = []
  for (const [entry, output] of [['main.ts', 'canvas-mcp.cjs'], ['call.ts', 'canvas-call.cjs']]) {
    results.push(await build({ entryPoints: [resolve(root, entry)], outfile: resolve(root, output), bundle: true, platform: 'node', format: 'cjs', target: 'node22', minify: true, legalComments: 'eof', metafile: true }))
  }
  const notices = new Map()
  for (const input of [...new Set(results.flatMap(result => Object.keys(result.metafile.inputs)))].filter(path => path.includes('node_modules/'))) {
    let directory = dirname(resolve(input))
    while (dirname(directory) !== directory) {
      const manifest = resolve(directory, 'package.json')
      if (existsSync(manifest)) {
        const pkg = JSON.parse(readFileSync(manifest, 'utf8'))
        if (pkg.name) {
          const license = ['LICENSE', 'LICENSE.md', 'LICENSE.txt'].map(name => resolve(directory, name)).find(existsSync)
          if (!license)
            throw new Error(`Missing dependency license: ${pkg.name}`)
          notices.set(`${pkg.name}@${pkg.version}`, readFileSync(license, 'utf8'))
          break
        }
      }
      directory = dirname(directory)
    }
  }
  writeFileSync(resolve(root, 'THIRD_PARTY_NOTICES.txt'), [...notices.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([name, text]) => `${name}\n${text}`).join('\n\n'))
}
main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
