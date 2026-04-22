<?php
/**
 * Chapitre 6 — affichage des lignes de la table `actions` (base db_objet).
 * Dans Docker Compose, le serveur MySQL s'appelle « db » sur le réseau interne.
 */
declare(strict_types=1);

header('Content-Type: text/html; charset=utf-8');

$dbHost = getenv('MYSQL_HOST') ?: 'db';
$dbUser = getenv('MYSQL_USER') ?: 'user';
$dbPass = getenv('MYSQL_PASSWORD') ?: 'pass';
$dbName = getenv('MYSQL_DATABASE') ?: 'db_objet';

$mysqli = @new mysqli($dbHost, $dbUser, $dbPass, $dbName);
if ($mysqli->connect_errno) {
    http_response_code(503);
    echo '<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8"><title>Erreur</title></head><body>';
    echo '<p>Connexion MySQL impossible. Vérifiez que le conteneur <code>db</code> tourne et que la base existe.</p>';
    echo '<p><small>' . htmlspecialchars($mysqli->connect_error, ENT_QUOTES, 'UTF-8') . '</small></p>';
    echo '</body></html>';
    exit(1);
}
$mysqli->set_charset('utf8mb4');

$sql = 'SELECT id_action, id_date, commande, valeur FROM actions ORDER BY id_date DESC, id_action DESC LIMIT 500';
$result = $mysqli->query($sql);
if ($result === false) {
    http_response_code(500);
    echo '<p>Requête SQL échouée : ' . htmlspecialchars($mysqli->error, ENT_QUOTES, 'UTF-8') . '</p>';
    $mysqli->close();
    exit(1);
}
?>
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PorteCoulissante — Actions</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 1.5rem; }
    h1 { font-size: 1.25rem; }
    table { border-collapse: collapse; width: 100%; max-width: 56rem; }
    th, td { border: 1px solid #ccc; padding: 0.4rem 0.6rem; text-align: left; }
    th { background: #1e3a5f; color: #fff; }
    tr:nth-child(even) { background: #f6f8fa; }
    .null { color: #666; font-style: italic; }
  </style>
</head>
<body>
  <h1>Table <code>actions</code> — historique des commandes</h1>
  <p>Base <code><?php echo htmlspecialchars($dbName, ENT_QUOTES, 'UTF-8'); ?></code></p>
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
<?php
while ($row = $result->fetch_assoc()) {
    $id = htmlspecialchars((string) $row['id_action'], ENT_QUOTES, 'UTF-8');
    $date = htmlspecialchars((string) $row['id_date'], ENT_QUOTES, 'UTF-8');
    $cmd = htmlspecialchars((string) $row['commande'], ENT_QUOTES, 'UTF-8');
    $val = $row['valeur'];
    $valCell = $val === null
        ? '<span class="null">NULL</span>'
        : htmlspecialchars((string) $val, ENT_QUOTES, 'UTF-8');
    echo "      <tr><td>{$id}</td><td>{$date}</td><td>{$cmd}</td><td>{$valCell}</td></tr>\n";
}
$result->free();
$mysqli->close();
?>
    </tbody>
  </table>
</body>
</html>
