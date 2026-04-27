<?php

/**
 * Point d'entrée dédié pour le proxy cloud (JSON).
 * Sur Azure App Service (nginx + PHP), les requêtes vers ce fichier sont
 * systématiquement exécutées par PHP, contrairement à /?api=... qui peut 404.
 */
declare(strict_types=1);

require_once __DIR__ . '/web_common.php';

run_cloud_api_proxy();
