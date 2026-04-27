<?php
/**
 * Application web de contrôle à distance.
 * - Affiche la télémétrie cloud (latest + historique)
 * - Envoie des commandes (auto/manuelle) vers l'API cloud
 * - Affiche les commandes en attente (confirmation objet)
 * - Garde la table locale MySQL "actions" pour le chapitre 6
 */
declare(strict_types=1);

require_once __DIR__ . '/web_common.php';

if (isset($_GET['api'])) {
    run_cloud_api_proxy();
}

$dbName = getenv('MYSQL_DATABASE') ?: 'db_objet';
$actions = [];
$dbError = null;
try {
    $db = connectDb();
    $actions = fetchRecentActions($db);
    $db->close();
} catch (WebAppException $exception) {
    $dbError = $exception->getMessage();
}
?>
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PorteCoulissante — Contrôle distant</title>
  <style>
    :root { color-scheme: light; }
    body { font-family: system-ui, sans-serif; margin: 1.2rem; background: #f7f9fc; color: #1f2d3d; }
    h1 { margin: 0 0 0.7rem; font-size: 1.45rem; }
    h2 { margin: 0 0 0.5rem; font-size: 1.05rem; }
    .card { background: #fff; border: 1px solid #d8e1ec; border-radius: 10px; padding: 0.9rem; margin-bottom: 0.9rem; }
    .row { display: flex; gap: 0.8rem; flex-wrap: wrap; }
    .grid-2 > div { flex: 1 1 320px; }
    .grid-3 > div { flex: 1 1 250px; }
    .muted { color: #5f6c7b; font-size: 0.92rem; }
    .warning { background: #fff3cd; color: #664d03; border-radius: 6px; padding: 0.6rem; margin-top: 0.5rem; }
    .error { background: #f8d7da; color: #842029; border-radius: 6px; padding: 0.6rem; margin-top: 0.5rem; }
    .success { background: #d1e7dd; color: #0f5132; border-radius: 6px; padding: 0.6rem; margin-top: 0.5rem; }
    .blinking-alert { animation: alertBlink 0.9s step-end infinite; }
    @keyframes alertBlink {
      0%, 50% { opacity: 1; }
      51%, 100% { opacity: 0.3; }
    }
    label { font-size: 0.9rem; color: #36495e; display: block; margin-bottom: 0.15rem; }
    input, select, button { font: inherit; padding: 0.4rem 0.55rem; border: 1px solid #c2cfde; border-radius: 7px; }
    button { cursor: pointer; background: #1d4f91; color: #fff; border-color: #1d4f91; }
    button.secondary { background: #f3f6fb; color: #223852; border-color: #c2cfde; }
    button:disabled { opacity: 0.6; cursor: not-allowed; }
    .value { font-size: 1.2rem; font-weight: 700; color: #183e72; }
    .small { font-size: 0.84rem; }
    table { border-collapse: collapse; width: 100%; font-size: 0.9rem; }
    th, td { border: 1px solid #d9e2ee; padding: 0.35rem 0.5rem; text-align: left; vertical-align: top; }
    th { background: #ecf3fb; }
    tr:nth-child(even) { background: #fafcff; }
  </style>
</head>
<body>
  <h1>PorteCoulissante — Application Web de contrôle à distance</h1>
  <p class="muted">API cloud: <code><?php echo safeText(resolveCloudApiBaseUrl()); ?></code></p>

  <section class="card">
    <div class="row grid-3">
      <div>
        <label for="deviceId">ID de l'objet</label>
        <input id="deviceId" type="text" value="porte_serre_01">
      </div>
      <div>
        <label for="manualValue">Consigne manuelle (%)</label>
        <input id="manualValue" type="number" min="0" max="100" step="1" value="56">
      </div>
      <div>
        <label for="autoRefresh">Rafraîchissement automatique</label>
        <select id="autoRefresh">
          <option value="off">Arrêté</option>
          <option value="3000" selected>3 secondes</option>
          <option value="5000">5 secondes</option>
          <option value="10000">10 secondes</option>
        </select>
      </div>
    </div>
    <div class="row" style="margin-top:0.8rem;">
      <button id="btnRefresh" type="button">Rafraîchir état</button>
      <button id="btnAuto" type="button">Mode automatique</button>
      <button id="btnOpen" type="button">Manuelle: Ouvrir</button>
      <button id="btnClose" type="button">Manuelle: Fermer</button>
      <button id="btnManualValue" type="button">Manuelle: Appliquer %</button>
    </div>
    <div id="commandFeedback" class="small muted" style="margin-top:0.6rem;">Aucune commande envoyée.</div>
  </section>

  <section class="card">
    <h2>État courant (télémétrie cloud)</h2>
    <div class="row grid-2">
      <div>
        <div class="small muted">Température</div>
        <div id="vTemp" class="value">--</div>
      </div>
      <div>
        <div class="small muted">Luminosité</div>
        <div id="vLight" class="value">--</div>
      </div>
      <div>
        <div class="small muted">Mode</div>
        <div id="vMode" class="value">--</div>
      </div>
      <div>
        <div class="small muted">Ouverture réelle</div>
        <div id="vRealOpen" class="value">--</div>
      </div>
      <div>
        <div class="small muted">Ouverture automatique calculée</div>
        <div id="vAutoOpen" class="value">--</div>
      </div>
      <div>
        <div class="small muted">Dernière réception</div>
        <div id="vLastTs" class="value">--</div>
      </div>
    </div>
    <div id="warningBox" class="warning" style="display:none;"></div>
    <div id="errorBox" class="error" style="display:none;"></div>
  </section>

  <section class="card">
    <h2>Commandes cloud en attente</h2>
    <table>
      <thead>
        <tr>
          <th>id</th>
          <th>date</th>
          <th>mode</th>
          <th>action</th>
          <th>valeur</th>
          <th>status</th>
        </tr>
      </thead>
      <tbody id="pendingRows">
        <tr><td colspan="6" class="muted">Aucune donnée.</td></tr>
      </tbody>
    </table>
  </section>

  <section class="card">
    <h2>Historique télémétrie (20 dernières)</h2>
    <table>
      <thead>
        <tr>
          <th>date</th>
          <th>température</th>
          <th>luminosité</th>
          <th>mode</th>
          <th>ouverture réelle</th>
          <th>ouverture auto</th>
          <th>erreur</th>
        </tr>
      </thead>
      <tbody id="historyRows">
        <tr><td colspan="7" class="muted">Aucune donnée.</td></tr>
      </tbody>
    </table>
  </section>

  <section class="card">
    <h2>Historique local MySQL — table <code>actions</code></h2>
<?php if ($dbError !== null): ?>
    <div class="error"><?php echo safeText($dbError); ?></div>
<?php else: ?>
    <p class="muted">Base <code><?php echo safeText((string) $dbName); ?></code></p>
    <table>
      <thead>
        <tr>
          <th>id_action</th>
          <th>id_date</th>
          <th>commande</th>
          <th>valeur</th>
        </tr>
      </thead>
      <tbody>
<?php if ($actions === []): ?>
        <tr><td colspan="4" class="muted">Aucune action locale.</td></tr>
<?php else: ?>
<?php foreach ($actions as $row): ?>
        <tr>
          <td><?php echo safeText((string) ($row['id_action'] ?? '')); ?></td>
          <td><?php echo safeText((string) ($row['id_date'] ?? '')); ?></td>
          <td><?php echo safeText((string) ($row['commande'] ?? '')); ?></td>
          <td><?php echo safeText((string) ($row['valeur'] ?? '')); ?></td>
        </tr>
<?php endforeach; ?>
<?php endif; ?>
      </tbody>
    </table>
<?php endif; ?>
  </section>

  <script>
    const state = {
      timerId: null,
    };

    function getDeviceId() {
      return document.getElementById('deviceId').value.trim();
    }

    function formatValue(value, unit = '') {
      if (value === null || value === undefined || value === '') return '--';
      return `${value}${unit}`;
    }

    function setText(id, value) {
      document.getElementById(id).textContent = value;
    }

    function showPanel(id, text) {
      const el = document.getElementById(id);
      el.classList.remove('blinking-alert');
      if (!text) {
        el.style.display = 'none';
        el.textContent = '';
        return;
      }
      el.style.display = 'block';
      el.textContent = text;
    }

    /**
     * Proxy JSON : fichier dédié api.php (routage fiable sur Azure nginx + PHP).
     */
    function buildLocalProxyUrl(action, deviceId) {
      const q = new URLSearchParams({ api: action, device_id: deviceId });
      return `/api.php?${q.toString()}`;
    }

    async function callLocalProxy(action, method = 'GET', body = null) {
      const deviceId = getDeviceId();
      if (!deviceId) throw new Error('ID de l\'objet requis.');
      const url = buildLocalProxyUrl(action, deviceId);
      const options = { method, headers: { 'Content-Type': 'application/json' } };
      if (body) {
        options.body = JSON.stringify(body);
      }
      const response = await fetch(url, options);
      const text = await response.text();
      let json;
      try {
        json = JSON.parse(text);
      } catch {
        const preview = text.replace(/\s+/g, ' ').trim().slice(0, 240);
        const hint = preview.startsWith('<')
          ? 'Le serveur a renvoyé du HTML (souvent une erreur PHP ou une page d’erreur), pas du JSON.'
          : 'Réponse invalide (pas du JSON).';
        throw new Error(`${hint} Extrait: ${preview || '(vide)'}`);
      }
      if (!response.ok || !json.ok) {
        const detail = json?.body?.detail || json?.error || 'Erreur API.';
        throw new Error(detail);
      }
      return json.body;
    }

    function parseTelemetryItem(payload) {
      if (!payload || !payload.item) return null;
      const item = payload.item;
      return item.body || null;
    }

    function renderLatestTelemetry(payload) {
      const body = parseTelemetryItem(payload);
      if (!body) {
        setText('vTemp', '--');
        setText('vLight', '--');
        setText('vMode', '--');
        setText('vRealOpen', '--');
        setText('vAutoOpen', '--');
        setText('vLastTs', '--');
        showPanel('warningBox', '');
        showPanel('errorBox', 'Aucune télémétrie trouvée pour cet objet.');
        return;
      }

      setText('vTemp', formatValue(body.temperature, ' °C'));
      setText('vLight', formatValue(body.luminosite, ' /100'));
      setText('vMode', formatValue(body.mode));
      setText('vRealOpen', formatValue(body.ouverture_reelle, ' %'));
      setText('vAutoOpen', formatValue(body.ouverture_automatique, ' %'));
      setText('vLastTs', formatValue(body.id_date));

      showPanel('warningBox', body.avertissement || '');
      showPanel('errorBox', body.erreur === 'oui' ? 'Anomalie détectée (erreur = oui).' : '');
      applyAlertBlinkingState(body);
    }

    function applyAlertBlinkingState(body) {
      const warningText = String(body?.avertissement || '').toLowerCase();
      const hasOpeningAnomaly = warningText.includes('ouverte plus que nécessaire')
        || warningText.includes('ouverte moins que nécessaire');
      if (!hasOpeningAnomaly) return;
      const warningPanel = document.getElementById('warningBox');
      const errorPanel = document.getElementById('errorBox');
      if (warningPanel.style.display !== 'none') warningPanel.classList.add('blinking-alert');
      if (errorPanel.style.display !== 'none') errorPanel.classList.add('blinking-alert');
    }

    function renderHistory(payload) {
      const rows = document.getElementById('historyRows');
      const items = Array.isArray(payload?.items) ? payload.items : [];
      if (items.length === 0) {
        rows.innerHTML = '<tr><td colspan="7" class="muted">Aucune donnée.</td></tr>';
        return;
      }
      rows.innerHTML = items.map((item) => {
        const body = item.body || {};
        return `<tr>
          <td>${body.id_date ?? '-'}</td>
          <td>${body.temperature ?? '-'} °C</td>
          <td>${body.luminosite ?? '-'}</td>
          <td>${body.mode ?? '-'}</td>
          <td>${body.ouverture_reelle ?? '-'} %</td>
          <td>${body.ouverture_automatique ?? '-'} %</td>
          <td>${body.erreur ?? '-'}</td>
        </tr>`;
      }).join('');
    }

    function renderPendingCommands(payload) {
      const rows = document.getElementById('pendingRows');
      const items = Array.isArray(payload?.items) ? payload.items : [];
      if (items.length === 0) {
        rows.innerHTML = '<tr><td colspan="6" class="muted">Aucune commande en attente.</td></tr>';
        return;
      }
      rows.innerHTML = items.map((item) => `<tr>
        <td>${item.id ?? '-'}</td>
        <td>${item.id_date ?? '-'}</td>
        <td>${item.commande ?? '-'}</td>
        <td>${item.action ?? '-'}</td>
        <td>${item.valeur ?? '-'}</td>
        <td>${item.status ?? '-'}</td>
      </tr>`).join('');
    }

    async function refreshAll() {
      try {
        const [latest, history, pending] = await Promise.all([
          callLocalProxy('latest'),
          callLocalProxy('history'),
          callLocalProxy('pending'),
        ]);
        renderLatestTelemetry(latest);
        renderHistory(history);
        renderPendingCommands(pending);
      } catch (error) {
        showPanel('errorBox', error.message || 'Erreur de rafraîchissement.');
      }
    }

    async function sendCommand(commandPayload, label) {
      const feedback = document.getElementById('commandFeedback');
      feedback.className = 'small muted';
      feedback.textContent = `Envoi: ${label}...`;
      try {
        const response = await callLocalProxy('command', 'POST', commandPayload);
        const commandId = response?.command?.id || '(id inconnu)';
        feedback.className = 'success small';
        feedback.textContent = `Commande envoyée (${label}). id=${commandId}`;
        await refreshAll();
      } catch (error) {
        feedback.className = 'error small';
        feedback.textContent = `Échec commande (${label}): ${error.message || error}`;
      }
    }

    function setupAutoRefresh() {
      const selected = document.getElementById('autoRefresh').value;
      if (state.timerId !== null) {
        clearInterval(state.timerId);
        state.timerId = null;
      }
      if (selected === 'off') return;
      const everyMs = Number(selected);
      state.timerId = setInterval(refreshAll, everyMs);
    }

    function parseManualPercent() {
      const raw = document.getElementById('manualValue').value;
      const number = Number(raw);
      if (!Number.isFinite(number) || number < 0 || number > 100) {
        throw new Error('La valeur manuelle doit être entre 0 et 100.');
      }
      return number;
    }

    document.getElementById('btnRefresh').addEventListener('click', () => { refreshAll(); });
    document.getElementById('autoRefresh').addEventListener('change', () => { setupAutoRefresh(); });
    document.getElementById('btnAuto').addEventListener('click', () => {
      sendCommand({ mode: 'automatique' }, 'mode automatique');
    });
    document.getElementById('btnOpen').addEventListener('click', () => {
      sendCommand({ mode: 'manuelle', action: 'ouvrir' }, 'ouvrir');
    });
    document.getElementById('btnClose').addEventListener('click', () => {
      sendCommand({ mode: 'manuelle', action: 'fermer' }, 'fermer');
    });
    document.getElementById('btnManualValue').addEventListener('click', () => {
      try {
        const value = parseManualPercent();
        sendCommand({ mode: 'manuelle', valeur: value }, `consigne ${value}%`);
      } catch (error) {
        const feedback = document.getElementById('commandFeedback');
        feedback.className = 'error small';
        feedback.textContent = error.message || String(error);
      }
    });

    setupAutoRefresh();
    refreshAll();
  </script>
</body>
</html>
