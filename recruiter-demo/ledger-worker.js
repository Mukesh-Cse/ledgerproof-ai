// A pinned Pyodide release runs the repository's Python and SQLite code off the UI thread.
const runtimeURL = 'https://cdn.jsdelivr.net/pyodide/v0.29.4/full/';
let runtime;

async function initRuntime() {
  const {loadPyodide} = await import(`${runtimeURL}pyodide.mjs`);
  const python = await loadPyodide({indexURL: runtimeURL});
  await python.loadPackage('sqlite3');
  for (const filename of ['payment_ledger.py', 'payment_sandbox.py']) {
    const response = await fetch(new URL(filename, import.meta.url));
    if (!response.ok) throw new Error(`Could not load ${filename}`);
    python.FS.writeFile(filename, await response.text());
  }
  python.runPython('import sys; sys.path.insert(0, "."); from payment_sandbox import compare_ledgers; import json');
  return python;
}

self.onmessage = async ({data}) => {
  let python;
  try {
    runtime ??= initRuntime();
    python = await runtime;
  } catch (error) {
    console.error('Could not start the SQLite browser engine:', error);
    self.postMessage({error: 'The Python and SQLite engine could not load. Check your connection and run again.'});
    return;
  }
  self.postMessage({phase: 'running'});
  try {
    python.globals.set('delivery_payload', JSON.stringify(data));
    const output = python.runPython('json.dumps(compare_ledgers(json.loads(delivery_payload)))');
    self.postMessage({result: JSON.parse(output)});
  } catch {
    self.postMessage({error: 'This run could not finish. Check the sample inputs or try a new run.'});
  } finally {
    python.globals.delete('delivery_payload');
  }
};
