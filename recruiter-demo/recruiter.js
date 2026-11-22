const examples = {
  collision: [['account-4', 'channel-7', 1200], ['account-9', 'channel-7', 850]],
  retry: [['account-4', 'channel-7', 1200], ['account-4', 'channel-7', 850]],
  distinct: [['account-4', 'channel-7', 1200], ['account-4', 'channel-8', 850]],
};
const element = id => document.getElementById(id);
const format = new Intl.NumberFormat('en');
const rows = element('delivery-rows');
const outcomes = element('booking-rows');
const limit = 12;
let worker;

function setStatus(text, error = false) {
  element('status').textContent = text;
  element('status').classList.toggle('error', error);
}

function clearResults() {
  element('results').hidden = true;
  setStatus('Run both ledgers to compare totals.');
}

function refreshControls() {
  Array.from(rows.rows).forEach((row, index) => {
    const number = index + 1;
    row.querySelectorAll('input').forEach(input => {
      input.setAttribute('aria-label', `${input.dataset.label} for delivery ${number}`);
    });
    row.querySelector('button').setAttribute('aria-label', `Remove delivery ${number}`);
    row.querySelector('button').disabled = rows.rows.length <= 1;
  });
  element('add').disabled = rows.rows.length >= limit;
}

function addDelivery(values) {
  const row = rows.insertRow();
  const fields = ['Account', 'Event ID', 'Minor units'];
  fields.forEach((label, index) => {
    const input = document.createElement('input');
    input.required = true;
    input.dataset.label = label;
    input.value = values[index];
    if (index === 2) {
      input.type = 'number';
      input.min = '1';
      input.max = '1000000000';
      input.step = '1';
    } else {
      input.maxLength = 40;
      input.autocomplete = 'off';
    }
    row.insertCell().append(input);
  });
  const remove = document.createElement('button');
  remove.type = 'button';
  remove.className = 'secondary';
  remove.textContent = '×';
  remove.addEventListener('click', () => {
    const nextRow = row.nextElementSibling ?? row.previousElementSibling;
    row.remove();
    refreshControls();
    clearResults();
    nextRow.querySelector('input').focus();
  });
  row.insertCell().append(remove);
  return row;
}

function loadExample() {
  rows.replaceChildren();
  examples[element('example').value].forEach(addDelivery);
  refreshControls();
  clearResults();
}

function compareInWorker(deliveries) {
  return new Promise((resolve, reject) => {
    worker ??= new Worker(new URL('./ledger-worker.js', import.meta.url), {type: 'module'});
    const finish = (error, result) => {
      clearTimeout(deadline);
      worker.onmessage = null;
      worker.onerror = null;
      if (error) {
        worker.terminate();
        worker = undefined;
        reject(new Error(error));
      } else resolve(result);
    };
    const deadline = setTimeout(() => finish('The browser engine took too long to start. Run again to retry.'), 45000);
    worker.onerror = () => finish('The browser engine could not load. Run again to retry.');
    worker.onmessage = ({data}) => {
      if (data.phase === 'running') setStatus('Running both SQLite ledgers…');
      else finish(data.error, data.result);
    };
    worker.postMessage(deliveries);
  });
}

function renderBookings(deliveries, result) {
  element('current-total').textContent = format.format(result.current.total_minor_units);
  element('faulty-total').textContent = format.format(result.faulty.total_minor_units);
  const delta = result.current.total_minor_units - result.faulty.total_minor_units;
  element('faulty-card').classList.toggle('difference', delta !== 0);
  outcomes.replaceChildren();
  deliveries.forEach(([account, eventId], index) => {
    const row = outcomes.insertRow();
    const identity = row.insertCell();
    identity.textContent = account;
    const eventLabel = document.createElement('small');
    eventLabel.textContent = eventId;
    identity.append(eventLabel);
    for (const variant of [result.current, result.faulty]) {
      const booking = variant.bookings[index];
      const cell = row.insertCell();
      cell.textContent = booking.booked ? 'Booked' : 'Suppressed';
      const detail = document.createElement('small');
      detail.textContent = booking.amount_matches
        ? `${format.format(booking.recorded_minor_units)} minor units`
        : `Kept ${format.format(booking.recorded_minor_units)} from the matched booking`;
      cell.append(detail);
    }
  });
  element('results').hidden = false;
  const magnitude = format.format(Math.abs(delta));
  if (delta === 0) setStatus('Both ledgers booked the same total.');
  else setStatus(`The faulty ledger booked ${magnitude} minor units ${delta > 0 ? 'less' : 'more'}.`);
}

element('example').addEventListener('change', loadExample);
rows.addEventListener('input', clearResults);
element('add').addEventListener('click', () => {
  if (rows.rows.length >= limit) return;
  const row = addDelivery(['', '', 100]);
  refreshControls();
  clearResults();
  row.querySelector('input').focus();
});
element('delivery-form').addEventListener('submit', async event => {
  event.preventDefault();
  if (element('run').disabled) return;
  const deliveries = Array.from(rows.rows, row => {
    const [account, eventId, amount] = row.querySelectorAll('input');
    return [account.value.trim(), eventId.value.trim(), amount.valueAsNumber];
  });
  if (deliveries.some(([account, eventId]) => !account || !eventId)) {
    setStatus('Enter an account and an event ID for each delivery.', true);
    return;
  }
  clearResults();
  setStatus(worker ? 'Running both SQLite ledgers…' : 'Loading the Python and SQLite browser engine…');
  element('editor').disabled = true;
  element('run').disabled = true;
  try {
    renderBookings(deliveries, await compareInWorker(deliveries));
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    element('editor').disabled = false;
    element('run').disabled = false;
  }
});

loadExample();
element('editor').disabled = false;
element('run').disabled = false;
