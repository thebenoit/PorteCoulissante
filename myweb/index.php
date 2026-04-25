<?php
/**
 * Application web de contrôle à distance.
 * - Affiche la télémétrie cloud (latest + historique)
 * - Envoie des commandes (auto/manuelle) vers l'API cloud
 * - Affiche les commandes en attente (confirmation objet)
 * - Garde la table locale MySQL "actions" pour le chapitre 6
 */
declare(strict_types=1);

const DEFAULT_CLOUD_API_BASE = 'https://projet-final-c5e4b5h8a3b4cqbx.eastus-01.azurewebsites.net';

final class WebAppException extends RuntimeException
{
}

function jsonResponse(int $status, array $payload): never
{
    http_response_code($status);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

function readJsonRequestBody(): array
{
    $raw = file_get_contents('php://input');
    if (!is_string($raw) || trim($raw) === '') {
        return [];
    }
    $decoded = json_decode($raw, true);
    return is_array($decoded) ? $decoded : [];
}

function resolveCloudApiBaseUrl(): string
{
    $envValue = getenv('CLOUD_API_BASE_URL');
    if (!is_string($envValue)) {
        return DEFAULT_CLOUD_API_BASE;
    }
    $normalized = trim($envValue);
    return $normalized !== '' ? rtrim($normalized, '/') : DEFAULT_CLOUD_API_BASE;
}

function buildCloudPath(string $route, string $deviceId): string
{
    return '/devices/' . rawurlencode($deviceId) . $route;
}

function createHttpContext(string $method, ?array $body): resource
{
    $headers = "Content-Type: application/json\r\n";
    $options = [
        'http' => [
            'method' => $method,
            'ignore_errors' => true,
            'timeout' => 8,
            'header' => $headers,
        ],
    ];
    if ($body !== null) {
        $options['http']['content'] = json_encode($body, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    }
    return stream_context_create($options);
}

function parseHttpStatus(array $httpResponseHeader): int
{
    $status = 502;
    if ($httpResponseHeader === []) {
        return $status;
    }
    $line = $httpResponseHeader[0] ?? '';
    if (is_string($line) && preg_match('/\s(\d{3})\s/', $line, $matches)) {
        $status = (int) $matches[1];
    }
    return $status;
}

function callCloudApi(string $method, string $path, ?array $body = null): array
{
    $baseUrl = resolveCloudApiBaseUrl();
    $url = $baseUrl . $path;
    $context = createHttpContext($method, $body);
    $raw = @file_get_contents($url, false, $context);
    $status = parseHttpStatus($http_response_header ?? []);
    $decoded = null;
    if (is_string($raw) && trim($raw) !== '') {
        $json = json_decode($raw, true);
        if (is_array($json)) {
            $decoded = $json;
        }
    }
    return ['status' => $status, 'data' => $decoded, 'raw' => is_string($raw) ? $raw : null, 'url' => $url];
}

function handleApiProxy(): never
{
    $action = isset($_GET['api']) ? trim((string) $_GET['api']) : '';
    $deviceId = isset($_GET['device_id']) ? trim((string) $_GET['device_id']) : '';
    if ($deviceId === '') {
        jsonResponse(400, ['ok' => false, 'error' => 'device_id est requis.']);
    }

    $method = 'GET';
    $path = '';
    $payload = null;
    if ($action === 'latest') {
        $path = buildCloudPath('/latest', $deviceId);
    } elseif ($action === 'history') {
        $path = buildCloudPath('/history?limit=20', $deviceId);
    } elseif ($action === 'pending') {
        $path = buildCloudPath('/commands/pending?limit=20', $deviceId);
    } elseif ($action === 'command') {
        $method = 'POST';
        $path = buildCloudPath('/commands', $deviceId);
        $payload = readJsonRequestBody();
    } else {
        jsonResponse(400, ['ok' => false, 'error' => 'Action API inconnue.']);
    }

    $response = callCloudApi($method, $path, $payload);
    $status = (int) $response['status'];
    $isSuccess = $status >= 200 && $status < 300;
    $body = is_array($response['data']) ? $response['data'] : ['raw' => $response['raw']];

    jsonResponse($status, [
        'ok' => $isSuccess,
        'status' => $status,
        'cloud_url' => $response['url'],
        'body' => $body,
    ]);
}

function connectDb(): mysqli
{
    $dbHost = getenv('MYSQL_HOST') ?: 'db';
    $dbUser = getenv('MYSQL_USER') ?: 'user';
    $dbPass = getenv('MYSQL_PASSWORD') ?: 'pass';
    $dbName = getenv('MYSQL_DATABASE') ?: 'db_objet';

    $mysqli = @new mysqli($dbHost, $dbUser, $dbPass, $dbName);
    if ($mysqli->connect_errno) {
        throw new WebAppException('Connexion MySQL impossible: ' . $mysqli->connect_error);
    }
    $mysqli->set_charset('utf8mb4');
    return $mysqli;
}

function fetchRecentActions(mysqli $db): array
{
    $sql = 'SELECT id_action, id_date, commande, valeur FROM actions ORDER BY id_date DESC, id_action DESC LIMIT 50';
    $result = $db->query($sql);
    if ($result === false) {
        throw new WebAppException('Requête SQL échouée: ' . $db->error);
    }

    $rows = [];
    while ($row = $result->fetch_assoc()) {
        $rows[] = $row;
    }
    $result->free();
    return $rows;
}

function safeText(string $value): string
{
    return htmlspecialchars($value, ENT_QUOTES, 'UTF-8');
}

if (isset($_GET['api'])) {
    handleApiProxy();
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
      if (!text) {
        el.style.display = 'none';
        el.textContent = '';
        return;
      }
      el.style.display = 'block';
      el.textContent = text;
    }

    async function callLocalProxy(action, method = 'GET', body = null) {
      const deviceId = getDeviceId();
      if (!deviceId) throw new Error('ID de l\'objet requis.');
      const url = `?api=${encodeURIComponent(action)}&device_id=${encodeURIComponent(deviceId)}`;
      const options = { method, headers: { 'Content-Type': 'application/json' } };
      if (body) {
        options.body = JSON.stringify(body);
      }
      const response = await fetch(url, options);
      const json = await response.json();
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
