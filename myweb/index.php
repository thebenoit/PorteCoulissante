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
    *, *::before, *::after { box-sizing: border-box; }
    :root { color-scheme: light; }
    body { font-family: system-ui, sans-serif; margin: 1.2rem; background: #f7f9fc; color: #1f2d3d; line-height: 1.45; }
    h1 { margin: 0 0 0.7rem; font-size: clamp(1.15rem, 4vw, 1.45rem); word-break: break-word; }
    h2 { margin: 0 0 0.5rem; font-size: clamp(1rem, 3vw, 1.05rem); }
    .card { background: #fff; border: 1px solid #d8e1ec; border-radius: 10px; padding: 0.9rem; margin-bottom: 0.9rem; max-width: 100%; }
    .row { display: flex; gap: 0.8rem; flex-wrap: wrap; }
    .grid-2 > div { flex: 1 1 320px; min-width: 0; }
    .grid-3 > div { flex: 1 1 250px; min-width: 0; }
    .muted { color: #5f6c7b; font-size: 0.92rem; }
    .muted code { word-break: break-all; }
    .warning { background: #fff3cd; color: #664d03; border-radius: 6px; padding: 0.6rem; margin-top: 0.5rem; word-break: break-word; }
    .error { background: #f8d7da; color: #842029; border-radius: 6px; padding: 0.6rem; margin-top: 0.5rem; word-break: break-word; }
    .success { background: #d1e7dd; color: #0f5132; border-radius: 6px; padding: 0.6rem; margin-top: 0.5rem; word-break: break-word; }
    .blinking-alert { animation: alertBlink 0.9s step-end infinite; }
    @keyframes alertBlink {
      0%, 50% { opacity: 1; }
      51%, 100% { opacity: 0.3; }
    }
    label { font-size: 0.9rem; color: #36495e; display: block; margin-bottom: 0.15rem; }
    input, select, button { font: inherit; padding: 0.45rem 0.6rem; border: 1px solid #c2cfde; border-radius: 7px; max-width: 100%; }
    input[type="text"], input[type="number"], select { width: 100%; min-height: 44px; }
    .btn-row { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.8rem; align-items: stretch; }
    button { cursor: pointer; background: #1d4f91; color: #fff; border-color: #1d4f91; min-height: 44px; touch-action: manipulation; }
    button.secondary { background: #f3f6fb; color: #223852; border-color: #c2cfde; }
    button:disabled { opacity: 0.6; cursor: not-allowed; }
    .value { font-size: clamp(1rem, 3.5vw, 1.2rem); font-weight: 700; color: #183e72; word-break: break-word; }
    .small { font-size: 0.84rem; }
    .table-scroll { width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch; margin: 0 -0.25rem; padding: 0 0.25rem; }
    table { border-collapse: collapse; width: 100%; font-size: 0.9rem; min-width: 520px; }
    th, td { border: 1px solid #d9e2ee; padding: 0.4rem 0.5rem; text-align: left; vertical-align: top; }
    th { background: #ecf3fb; white-space: nowrap; }
    tr:nth-child(even) { background: #fafcff; }

    @media (max-width: 640px) {
      body { margin: 0.75rem; }
      .card { padding: 0.75rem; border-radius: 8px; }
      .grid-2 > div, .grid-3 > div { flex: 1 1 100%; }
      .btn-row button { flex: 1 1 calc(50% - 0.25rem); min-width: 8rem; }
      table { font-size: 0.82rem; min-width: 480px; }
      th, td { padding: 0.35rem 0.4rem; }
    }

    @media (max-width: 380px) {
      .btn-row button { flex: 1 1 100%; }
    }
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
    <div class="btn-row">
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
    <div class="table-scroll">
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
    </div>
  </section>

  <section class="card">
    <h2>Historique télémétrie (20 dernières)</h2>
    <div class="table-scroll">
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
    </div>
  </section>

  <section class="card">
    <h2>Historique local MySQL — table <code>actions</code></h2>
<?php if ($dbError !== null): ?>
    <div class="error"><?php echo safeText($dbError); ?></div>
<?php else: ?>
    <p class="muted">Base <code><?php echo safeText((string) $dbName); ?></code></p>
    <div class="table-scroll">
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
    </div>
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
     * Proxy : POST JSON vers /api.php (sans paramètres sensibles en query) pour éviter
     * les règles de filtrage (WAF) d’Azure sur certaines query strings.
     */
    async function callLocalProxy(action, _method = 'POST', body = null) {
      const deviceId = getDeviceId();
      if (!deviceId) throw new Error('ID de l\'objet requis.');
      const payload = { action, device_id: deviceId };
      if (action === 'command' && body !== null && typeof body === 'object') {
        payload.command = body;
      }
      const response = await fetch('/api.php', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
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
