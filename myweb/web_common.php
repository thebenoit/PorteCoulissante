<?php

declare(strict_types=1);

const DEFAULT_CLOUD_API_BASE = 'https://projet-final-c5e4b5h8a3b4cqbx.eastus-01.azurewebsites.net';

final class WebAppException extends RuntimeException
{
}

function discardAnyPhpOutputBuffers(): void
{
    while (ob_get_level() > 0) {
        ob_end_clean();
    }
}

function jsonResponse(int $status, array $payload): never
{
    discardAnyPhpOutputBuffers();
    http_response_code($status);
    header('Content-Type: application/json; charset=utf-8');
    $encoded = json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    echo $encoded !== false ? $encoded : '{"ok":false,"error":"Encodage JSON impossible."}';
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

function createHttpContext(string $method, ?array $body)
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
    if (filter_var(ini_get('allow_url_fopen'), FILTER_VALIDATE_BOOLEAN) !== true) {
        return [
            'status' => 503,
            'data' => null,
            'raw' => null,
            'url' => resolveCloudApiBaseUrl() . $path,
            'error' => 'allow_url_fopen est désactivé: impossible d’appeler l’API cloud depuis PHP.',
        ];
    }

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
    if (isset($response['error']) && is_string($response['error'])) {
        $body['detail'] = $response['error'];
    }

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

    try {
        $mysqli = @new mysqli($dbHost, $dbUser, $dbPass, $dbName);
    } catch (Throwable $exception) {
        throw new WebAppException('Connexion MySQL impossible: ' . $exception->getMessage());
    }
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

function run_cloud_api_proxy(): void
{
    ini_set('display_errors', '0');
    ob_start();
    try {
        handleApiProxy();
    } catch (Throwable $exception) {
        jsonResponse(500, [
            'ok' => false,
            'error' => $exception->getMessage(),
            'body' => null,
        ]);
    }
}
