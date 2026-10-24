# TODO

Retours sur la 0.10.0 en production (22/10/2026).

## Bugs

- [x] `GET /api/v1/library/series/<id>` répond 503.
- [x] La fenêtre de la fiche d'une série a un double scroll.
- [x] La recherche ne doit pas partir quand la barre de recherche est vide.
- [x] Quand on quitte la page de recherche puis qu'on y revient, ne pas garder la recherche précédente, ou alors la garder sans la relancer.
- [x] Pouvoir effacer toute la recherche (texte, filtres et résultats), pas seulement le texte tapé.

## Fonctionnalités

- [ ] Ajouter les couvertures sur les titres envoyés automatiquement : dans les messages Discord (« Envoyé », « Téléchargé ») et dans la page Téléchargements.
- [ ] Une page par section, où seule la vue change, pour avoir un vrai historique de navigation (retour / avance du navigateur, liens directs).
- [ ] Catégories des indexeurs :
  - [x] retirer le filtre sur le nom des releases (`cbz`, etc.) s'il existe : il n'existe pas. Une release n'est écartée que sans seed, en doublon, quand son titre n'a pas tous les mots significatifs du nom cherché (recherche automatique seulement, `is_relevant`), ou par les règles de l'onglet Filtres (aucune en production).
  - [x] si ce n'est pas déjà le cas, prendre les trackers depuis les indexeurs réels de Prowlarr, sans filtre : c'est le cas (`GET /api/v1/indexer`, seuls les indexeurs usenet sont écartés, qBittorrent ne prend que des torrents).
  - [ ] pouvoir choisir sur le site, pour chaque indexeur, la ou les catégories à utiliser et à quel type elles correspondent (par exemple Nyaa : « Literature » pour les mangas). Une ou plusieurs catégories par type. Aujourd'hui elles sont figées dans le code (`CATEGORIES` de `shelfdrop/releases/types.py` : 7030 Manga & BD, 7020 Livre, 3030 Livre audio) : une release qu'un tracker range ailleurs ne revient jamais. Il faut lire les catégories de chaque tracker dans Prowlarr (`capabilities.categories`).
- [ ] Servir la vraie doc d'API générée par FastAPI (Swagger UI / ReDoc depuis l'OpenAPI) à la place de la page actuelle de `/api/docs`. Elle ne décrit que l'API publique (accès par jeton) : rien sur la partie session du site.
- [x] Journal Discord : ne plus mettre d'adresse IP dans les embeds (champ « Adresse IP » du message « Connexion »).
- [ ] Bibliothèque : voir le contenu d'une série (les tomes qu'on a, avec leur couverture, leur numéro et leur taille, et les tomes manquants) et pouvoir télécharger chaque fichier depuis le site.
- [ ] Pouvoir lire les logs depuis le site.
- [ ] Compte interne et panneau d'installation initial (à faire ensemble) :
  - un compte interne (admin propre à shelfdrop) pour se connecter quand Jellyfin n'est pas encore branché, et les textes de la page de connexion revus en conséquence (aujourd'hui elle ne parle que du compte Jellyfin) ;
  - un vrai panneau d'installation au premier lancement : création de ce compte, puis branchement pas à pas de Prowlarr, qBittorrent et Jellyfin (avec leur test), des bibliothèques et du dossier des envois, avant d'ouvrir le reste du site.
- [ ] Fichiers non reconnus dans un torrent : quand le rangement ne sait pas à quoi correspond un fichier (tome, chapitre, piste…), pouvoir lui indiquer quoi en faire depuis le site, fichier par fichier, comme l'import manuel de Sonarr (choisir l'œuvre, le tome ou les chapitres, ou ignorer le fichier), puis ranger.
- [ ] Forcer la synchronisation des métadonnées de shelfdrop vers Jellyfin (nom, série, numéro, auteurs, couverture, verrouillage), pour une série ou pour toute la bibliothèque, depuis le site. La couverture des tomes reste celle de Jellyfin.

## Documentation

- [ ] Toute la doc (README, `docs/`, ADR, doc d'API) doit être écrite pour une utilisation générale de shelfdrop, pas pour notre installation : pas de domaine, de machine, d'adresse ou d'agent qui nous sont propres dans les descriptions (aujourd'hui : `docs/installation.md`, `docs/api.md`, `docs/configuration.md`, `docs/verified-facts.md`, `docs/hermes.md`, ADR 0002 et 0008, ainsi que « the user » partout). Nos valeurs vont au mieux en exemple clairement marqué comme tel.
  - Même chose pour les outils autour : ne pas décrire Cloudflare, nginx, WireGuard, ufw… comme faisant partie de l'installation. **Docker est le seul outil à décrire** ; le reste (proxy, tunnel, pare-feu) se limite à ce que shelfdrop attend (en-têtes, taille des requêtes, délais), sans nommer de produit. Les services que l'app appelle elle-même (Prowlarr, qBittorrent, Jellyfin) restent documentés.

## Interface

- [ ] Faire le front en mobile first.
- [x] Les boutons n'ont parfois pas la même taille que les composants à côté.
- [x] Paramètres : aligner « Enregistré » et « Tout testé ».
- [x] Renommer la section « Métadonnées » en « Jellyfin ».
- [x] Catégories : renommer « Manga » en « Manga & BD ».
