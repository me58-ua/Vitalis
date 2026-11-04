import { spawnSync } from 'node:child_process';
import { existsSync, writeFileSync } from 'node:fs';
import { fileURLToPath, URL } from 'node:url';
import path from 'node:path';

const root = fileURLToPath(new URL('../', import.meta.url));
const backend = path.resolve(root, '../backend');
const localPython = path.join(backend, 'venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const python = process.env.VITALIS_PYTHON || (existsSync(localPython) ? localPython : 'python');
// Importing the app does not start its lifespan or query patient data.
const result = spawnSync(python, ['-c', 'import json; from app.main import app; print(json.dumps(app.openapi()))'], {
  cwd: backend, encoding: 'utf8', maxBuffer: 10 * 1024 * 1024,
});
if (result.status !== 0) {
  // Do not echo Python errors: configuration validation can contain secret values.
  console.error('No se pudo exportar OpenAPI. Revisa el entorno Python y la configuración del backend.');
  process.exit(1);
}
const schema = JSON.parse(result.stdout);
writeFileSync(path.join(root, 'openapi.json'), `${JSON.stringify(schema, null, 2)}\n`);
console.log(`OpenAPI ${schema.openapi}: ${Object.keys(schema.paths).length} rutas exportadas.`);
