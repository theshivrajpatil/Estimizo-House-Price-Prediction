const form = document.querySelector('#prediction-form');
const predictButton = document.querySelector('#predict-button');
const errorBox = document.querySelector('#form-error');
const emptyResult = document.querySelector('#result-empty');
const resultContent = document.querySelector('#result-content');
const resetButton = document.querySelector('#reset-button');
const menuToggle = document.querySelector('#menu-toggle');
const nav = document.querySelector('#main-nav');

const locations = {
  'san-francisco': { name: 'San Francisco', longitude: -122.42, latitude: 37.77, ocean: 'NEAR BAY' },
  'san-jose': { name: 'San Jose', longitude: -121.89, latitude: 37.34, ocean: 'NEAR BAY' },
  oakland: { name: 'Oakland', longitude: -122.27, latitude: 37.80, ocean: 'NEAR BAY' },
  'los-angeles': { name: 'Los Angeles', longitude: -118.24, latitude: 34.05, ocean: '<1H OCEAN' },
  'san-diego': { name: 'San Diego', longitude: -117.16, latitude: 32.72, ocean: 'NEAR OCEAN' },
  'santa-barbara': { name: 'Santa Barbara', longitude: -119.70, latitude: 34.42, ocean: 'NEAR OCEAN' },
  sacramento: { name: 'Sacramento', longitude: -121.49, latitude: 38.58, ocean: 'INLAND' },
  fresno: { name: 'Fresno', longitude: -119.79, latitude: 36.74, ocean: 'INLAND' }
};

menuToggle.addEventListener('click', () => {
  const open = nav.classList.toggle('open');
  menuToggle.setAttribute('aria-expanded', String(open));
  menuToggle.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
});
nav.querySelectorAll('a').forEach(link => link.addEventListener('click', () => {
  nav.classList.remove('open');
  menuToggle.setAttribute('aria-expanded', 'false');
}));

function showError(message) {
  errorBox.textContent = message;
  errorBox.hidden = false;
}
function clearError() {
  errorBox.textContent = '';
  errorBox.hidden = true;
}
function formatUSD(value) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(value);
}
function resetResult() {
  resultContent.hidden = true;
  emptyResult.hidden = false;
  clearError();
}

const budgetSelect = document.querySelector('#budget');
const areaInput = form.elements.area;
const locationSelect = form.elements.location;
const bedroomsSelect = form.elements.bedrooms;
const bathroomsSelect = form.elements.bathrooms;
let budgetRefreshTimer;

function formatCompactUSD(value) {
  if (value >= 1000000) return `$${(value / 1000000).toFixed(value % 1000000 === 0 ? 0 : 1)}M`;
  return `$${Math.round(value / 1000)}k`;
}

function setBudgetOptions(lower, typical, upper) {
  const midLow = Math.round((lower + typical) / 2 / 5000) * 5000;
  const midHigh = Math.round((typical + upper) / 2 / 5000) * 5000;
  const options = [
    ['', 'Choose a target budget'],
    [`under-${Math.round(lower)}`, `Below ${formatCompactUSD(lower)}`],
    [`${Math.round(lower)}-${midLow}`, `${formatCompactUSD(lower)} – ${formatCompactUSD(midLow)}`],
    [`${midLow}-${midHigh}`, `${formatCompactUSD(midLow)} – ${formatCompactUSD(midHigh)}`],
    [`${midHigh}-${Math.round(upper)}`, `${formatCompactUSD(midHigh)} – ${formatCompactUSD(upper)}`],
    [`over-${Math.round(upper)}`, `Above ${formatCompactUSD(upper)}`]
  ];
  budgetSelect.replaceChildren(...options.map(([value, label]) => {
    const option = document.createElement('option');
    option.value = value;
    option.textContent = label;
    return option;
  }));
}

async function refreshBudgetOptions() {
  const locationKey = locationSelect.value;
  const area = Number(areaInput.value);
  if (!locationKey || !Number.isFinite(area) || area < 250) {
    budgetSelect.replaceChildren(new Option('Choose location and area first', ''));
    return;
  }
  try {
    const response = await fetch('/estimate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        location: locationKey,
        area,
        bedrooms: Number(bedroomsSelect.value) || 3,
        bathrooms: Number(bathroomsSelect.value) || 2
      })
    });
    const result = await response.json();
    if (response.ok && Number.isFinite(Number(result.lower)) && Number.isFinite(Number(result.upper))) {
      setBudgetOptions(Number(result.lower), Number(result.prediction), Number(result.upper));
    }
  } catch (_) {
    budgetSelect.replaceChildren(new Option('Budget options unavailable', ''));
  }
}

function scheduleBudgetRefresh() {
  clearTimeout(budgetRefreshTimer);
  budgetRefreshTimer = setTimeout(refreshBudgetOptions, 250);
}
[locationSelect, areaInput, bedroomsSelect, bathroomsSelect].forEach(input => {
  input.addEventListener('change', scheduleBudgetRefresh);
  input.addEventListener('input', scheduleBudgetRefresh);
});

form.addEventListener('submit', async event => {
  event.preventDefault();
  clearError();
  const data = new FormData(form);
  const locationKey = String(data.get('location') || '');
  const location = locations[locationKey];
  const area = Number(data.get('area'));
  const bedrooms = Number(data.get('bedrooms'));
  const bathrooms = Number(data.get('bathrooms'));

  if (!location || !Number.isFinite(area) || area < 250 || area > 20000 || !bedrooms || !bathrooms) {
    showError('Please complete each required property detail with a valid value.');
    return;
  }

  predictButton.disabled = true;
  predictButton.innerHTML = 'Preparing estimate <span>…</span>';
  try {
    const response = await fetch('/estimate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ location: locationKey, area, bedrooms, bathrooms })
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.error || 'We could not prepare the estimate right now. Please try again.');
    const prediction = Number(body.prediction);
    const lower = Number(body.lower);
    const upper = Number(body.upper);
    if (![prediction, lower, upper].every(Number.isFinite)) {
      throw new Error('The estimate service returned an unexpected result. Please try again.');
    }

    document.querySelector('#predicted-price').textContent = formatUSD(prediction);
    document.querySelector('#price-range').textContent = `Typical range: ${formatUSD(lower)} – ${formatUSD(upper)}`;
    document.querySelector('#result-location').textContent = location.name;
    document.querySelector('#result-area').textContent = `${area.toLocaleString('en-US')} sq. ft.`;
    document.querySelector('#result-rooms').textContent = `${bedrooms} bed · ${bathrooms} bath`;
    emptyResult.hidden = true;
    resultContent.hidden = false;
  } catch (error) {
    showError(error.message === 'Failed to fetch'
      ? 'Could not connect to the estimator. Please make sure the website server is running, then try again.'
      : error.message || 'Unable to prepare an estimate. Please try again.');
  } finally {
    predictButton.disabled = false;
    predictButton.innerHTML = 'Get price estimate <span>↗</span>';
  }
});

resetButton.addEventListener('click', () => {
  form.reset();
  budgetSelect.replaceChildren(new Option('Choose location and area first', ''));
  document.querySelector('#price-range').textContent = '';
  resetResult();
  form.elements.location.focus();
});

const queryForm = document.querySelector('#query-form');
const contactSubmit = document.querySelector('#contact-submit');
const contactStatus = document.querySelector('#contact-status');

queryForm.addEventListener('submit', async event => {
  event.preventDefault();
  const data = new FormData(queryForm);
  const payload = Object.fromEntries(data.entries());
  contactSubmit.disabled = true;
  contactSubmit.innerHTML = 'Sending… <span>↗</span>';
  contactStatus.textContent = 'Sending your message securely…';
  contactStatus.classList.remove('status-error', 'status-success');

  try {
    const response = await fetch('/contact', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Your message could not be sent.');
    contactStatus.textContent = 'Message sent successfully. Thank you for reaching out!';
    contactStatus.classList.add('status-success');
    queryForm.reset();
  } catch (error) {
    contactStatus.textContent = error.message === 'Failed to fetch'
      ? 'Could not connect to the website. Please check that the server is running and try again.'
      : error.message || 'Unable to send your message. Please try again later.';
    contactStatus.classList.add('status-error');
  } finally {
    contactSubmit.disabled = false;
    contactSubmit.innerHTML = 'Send message <span>↗</span>';
  }
});
