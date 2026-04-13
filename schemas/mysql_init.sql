-- Chapitre 6 — tables TP (db_objet)
-- Exécuter dans phpMyAdmin (onglet SQL) ou : mysql -u user -p db_objet < schemas/mysql_init.sql

USE db_objet;

CREATE TABLE IF NOT EXISTS actions (
  id_action BIGINT PRIMARY KEY AUTO_INCREMENT,
  id_date DATETIME NOT NULL,
  commande ENUM('automatique','manuelle','ouvrir','fermer') NOT NULL,
  valeur DECIMAL(5,2) NULL
);

CREATE TABLE IF NOT EXISTS events (
  id_event BIGINT PRIMARY KEY AUTO_INCREMENT,
  id_date DATETIME NOT NULL,
  moteur ENUM('demarrer','arreter') NOT NULL,
  direction ENUM('gauche','droite') NULL,
  vitesse DECIMAL(6,2) NULL,
  distance DECIMAL(6,2) NULL,
  erreur ENUM('oui','non') NOT NULL DEFAULT 'non',
  avertissement TEXT NULL
);

CREATE TABLE IF NOT EXISTS messages_envoyes (
  id_message CHAR(36) PRIMARY KEY,
  id_objet VARCHAR(64) NOT NULL,
  id_date DATETIME NOT NULL,
  status ENUM('envoye','en_attente') NOT NULL DEFAULT 'en_attente',
  temperature DECIMAL(5,2) NOT NULL,
  luminosite DECIMAL(5,2) NOT NULL,
  ouverture_automatique DECIMAL(5,2) NOT NULL,
  mode ENUM('manuelle','automatique') NOT NULL,
  ouverture_reelle DECIMAL(5,2) NOT NULL,
  erreur ENUM('oui','non') NOT NULL DEFAULT 'non',
  avertissement TEXT NULL
);

CREATE TABLE IF NOT EXISTS messages_recus (
  id_message CHAR(36) PRIMARY KEY,
  id_objet VARCHAR(64) NOT NULL,
  id_date DATETIME NOT NULL,
  status ENUM('accomplit','en_attente') NOT NULL DEFAULT 'en_attente',
  commande ENUM('manuelle','automatique') NOT NULL,
  valeur DECIMAL(5,2) NULL
);
