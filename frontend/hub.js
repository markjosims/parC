import { fetchGrammarHealth, fetchGrammarStats, recompileGrammar } from './api.js';

let lastHealth = null;
let lastStats = null;
let isFetching = false;

const statusDot = document.querySelector('.status-dot');
const statusLabel = document.querySelector('.status-label');
const statsSection = document.getElementById('stats-section');
const statsGrid = document.getElementById('stats-grid');
const recompileBtn = document.getElementById('recompile-btn');


const CARD_GROUPS = {
  Phonology: {
    inventory: {
      title: 'Inventory',
      format: (d) => [`${d.files} files`, `${d.phones} phones`, `${d.tags} tags`, `${d.classes} classes`]
    },
    patterns: {
      title: 'Patterns',
      format: (d) => [`${d.files} files`, `${d.total} patterns`]
    },
    rules: {
      title: 'Rules',
      format: (d) => [`${d.files} files`, `${d.total} rules`]
    },
  },
  Exponence: {
    feature_definitions: {
      title: 'Feat. Definitions',
      format: (d) => [`${d.files} files`, `${d.total} features`]
    },
    feature_markers: {
      title: 'Feat. Markers',
      format: (d) => [`${d.files} files`, `${d.total} markers`]
    },
    contingent_markers: {
      title: 'Cont. Markers',
      format: (d) => [`${d.files} files`, `${d.total} markers`]
    },
  },
  Lexicon: {
    part_of_speech: {
      title: 'Part of Sp.',
      format: (d) => [`${d.files} files`, `${d.total} lexemes`]
    },  
  },
  Morphotactics: {
    paradigms: {
      title: 'Paradigms',
      format: (d) => [`${d.files} files`, `${d.total} paradigms`]
    },
  },
};

function updateStatusUI(status) {
  statusDot.className = 'status-dot ' + status;
  if (status === 'loaded') statusLabel.textContent = 'Loaded';
  else if (status === 'unloaded') statusLabel.textContent = 'Not loaded';
  else if (status === 'error') statusLabel.textContent = 'Load error';
  else statusLabel.textContent = 'Checking…';
}

function renderStats(stats, isStale) {
  if (!stats) {
    statsSection.setAttribute('hidden', '');
    return;
  }
  statsSection.removeAttribute('hidden');
  
  if (isStale) {
    statsGrid.classList.add('stale');
  } else {
    statsGrid.classList.remove('stale');
  }

  statsGrid.innerHTML = '';
  for (const [groupName, cards] of Object.entries(CARD_GROUPS)) {
    const groupEl = document.createElement('div');
    groupEl.className = 'stats-group';

    const heading = document.createElement('h4');
    heading.className = 'stats-group-title';
    heading.textContent = groupName;
    groupEl.appendChild(heading);

    const cardsEl = document.createElement('div');
    cardsEl.className = 'stats-group-cards';

    for (const [key, meta] of Object.entries(cards)) {
      const data = stats[key];
      if (!data) continue;

      const card = document.createElement('div');
      card.className = 'stat-card';

      const title = document.createElement('h5');
      title.textContent = meta.title;
      card.appendChild(title);

      const list = document.createElement('ul');
      meta.format(data).forEach(line => {
        const li = document.createElement('li');
        li.textContent = line;
        list.appendChild(li);
      });
      card.appendChild(list);
      cardsEl.appendChild(card);
    }

    groupEl.appendChild(cardsEl);
    statsGrid.appendChild(groupEl);
  }
}

async function checkGrammar() {
  if (isFetching) return;
  isFetching = true;

  let health = 'checking';
  let stats = null;

  try {
    const healthRes = await fetchGrammarHealth();
    health = healthRes.status;
  } catch {
    health = 'unloaded';
  }

  if (health === 'loaded') {
    try {
      stats = await fetchGrammarStats();
    } catch (err) {
      health = err.status === 503 ? 'error' : 'unloaded';
    }
  }

  lastHealth = health;
  if (stats) lastStats = stats;

  updateStatusUI(health);
  renderStats(lastStats, health !== 'loaded');
  isFetching = false;
}

recompileBtn.addEventListener('click', async () => {
  recompileBtn.disabled = true;
  recompileBtn.textContent = 'Recompiling...';
  try {
    await recompileGrammar();
  } catch (err) {
    alert(err.message);
  } finally {
    recompileBtn.disabled = false;
    recompileBtn.textContent = 'Recompile';
    await checkGrammar();
  }
});

checkGrammar();
setInterval(checkGrammar, 5000);

