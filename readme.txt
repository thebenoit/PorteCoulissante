PorteCoulissante — Projet final Objets connectés (H26)
======================================================

Prérequis
---------
- Docker et Docker Compose (MySQL + phpMyAdmin + Apache/PHP)
- Python 3.11+ sur le Raspberry Pi (ou PC en simulation)
- Compte Azure : IoT Hub, Cosmos DB (pour l’API cloud)

Installation
------------
1) Base de données
   docker compose up -d
   Initialiser les tables : exécuter schemas/mysql_init.sql dans phpMyAdmin
   (base db_objet, utilisateur/mot de passe selon docker-compose.yml).

2) Application Python (objet)
   cp .env.example .env
   Renseigner DB_* et IOTHUB_DEVICE_CONNECTION_STRING (et optionnellement COSMOS_*).
   Sur Raspberry Pi avec ADC I2C :
     python3 -m venv --system-site-packages .venv
     sudo apt install python3-smbus i2c-tools
   source .venv/bin/activate
   pip install -r requirements.txt
   python3 main.py

3) Site PHP (liste des actions, chapitre 6)
   Ouvrir http://localhost:9999 après docker compose (table actions remplie).

4) API cloud (FastAPI)
   source .venv/bin/activate
   Renseigner COSMOS_ENDPOINT et COSMOS_KEY dans .env.
   uvicorn cloud_api:app --host 0.0.0.0 --port 8000
   Documentation interactive : http://localhost:8000/docs

Fichiers utiles
---------------
- main.py              : interface Tkinter + contrôle porte
- cloud_api.py         : API lecture télémétrie / commandes Cosmos
- docker-compose.yml   : stack MySQL + phpMyAdmin + web
- documents/RAPPORT-Projet-final-H26.md : rapport de projet
