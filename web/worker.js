// Module Web Worker that runs the laserdesign Python package under Pyodide, so the
// page stays responsive while a design is computed.
//
// Messages in:  {id, cmd: "init", config} | {id, cmd: "catalog"} |
//               {id, cmd: "normalise", spec} | {id, cmd: "run", spec, step}
// Messages out: {id, result} | {id, error} | {status: text}

let pyodide = null;
let api = null;

function status(text) {
  self.postMessage({ status: text });
}

async function init(config) {
  const indexURL = config.pyodideIndexURL;
  status("Loading the Python runtime…");
  const { loadPyodide } = await import(indexURL + "pyodide.mjs");
  pyodide = await loadPyodide({ indexURL });
  status("Loading NumPy and SciPy…");
  await pyodide.loadPackage(["numpy", "scipy"], { messageCallback: () => {} });
  status("Loading laserdesign…");
  const resp = await fetch(config.packageURL);
  if (!resp.ok) throw new Error(`Could not fetch ${config.packageURL} (${resp.status})`);
  const buf = await resp.arrayBuffer();
  pyodide.unpackArchive(buf, "zip", { extractDir: "/home/pyodide/site" });
  pyodide.runPython(`
import sys
sys.path.insert(0, "/home/pyodide/site")
import laserdesign.web.api as api
`);
  api = pyodide.globals.get("api");
  return { python: pyodide.runPython("import sys; sys.version.split()[0]"),
           pyodide: pyodide.version };
}

self.onmessage = async (ev) => {
  const { id, cmd } = ev.data;
  try {
    let result;
    if (cmd === "init") result = await init(ev.data.config);
    else if (cmd === "catalog") result = JSON.parse(api.catalog());
    else if (cmd === "normalise") result = JSON.parse(api.normalise(JSON.stringify(ev.data.spec)));
    else if (cmd === "run") result = JSON.parse(api.run(JSON.stringify(ev.data.spec), ev.data.step));
    else throw new Error(`Unknown command ${cmd}`);
    self.postMessage({ id, result });
  } catch (err) {
    self.postMessage({ id, error: String(err && err.message ? err.message : err) });
  }
};
