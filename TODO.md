# TODO

Retours sur la 0.10.0 en production (22/10/2026).

## Bugs

- [ ] `GET /api/v1/library/series/<id>` répond 503.
- [ ] La fenêtre de la fiche d'une série a un double scroll.
- [ ] La recherche ne doit pas partir quand la barre de recherche est vide.
- [ ] Quand on quitte la page de recherche puis qu'on y revient, ne pas garder la recherche précédente, ou alors la garder sans la relancer.
- [ ] Pouvoir effacer toute la recherche (texte, filtres et résultats), pas seulement le texte tapé.

## Fonctionnalités

- [ ] Ajouter les couvertures sur les titres envoyés automatiquement.
- [ ] Une page par section, où seule la vue change, pour avoir un vrai historique de navigation (retour / avance du navigateur, liens directs).
- [ ] Catégories des indexeurs :
  - retirer le filtre sur le nom des releases (`cbz`, etc.) s'il existe ;
  - si ce n'est pas déjà le cas, prendre les trackers depuis les indexeurs réels de Prowlarr, sans filtre ;
  - pouvoir choisir sur le site, pour chaque indexeur, la ou les catégories à utiliser et à quel type elles correspondent (par exemple Nyaa : « Literature » pour les mangas). Une ou plusieurs catégories par type.
- [ ] Servir la vraie doc d'API générée par FastAPI (Swagger UI / ReDoc depuis l'OpenAPI) à la place de la page actuelle de `/api/docs`. Elle ne décrit que l'API publique (accès par jeton) : rien sur la partie session du site.
- [ ] Journal Discord : ne plus mettre d'adresse IP dans les embeds (champ « Adresse IP » du message « Connexion »).
- [ ] Bibliothèque : voir un aperçu des fichiers rangés et pouvoir les télécharger depuis le site.
- [ ] Pouvoir lire les logs depuis le site.

## Documentation

- [ ] Toute la doc (README, `docs/`, ADR, doc d'API) doit être écrite pour une utilisation générale de shelfdrop, pas pour notre installation : pas de domaine, de machine, d'adresse ou d'agent qui nous sont propres dans les descriptions (aujourd'hui : `docs/installation.md`, `docs/api.md`, `docs/configuration.md`, `docs/verified-facts.md`, `docs/hermes.md`, ADR 0002 et 0008, ainsi que « the user » partout). Nos valeurs vont au mieux en exemple clairement marqué comme tel.

## Interface

- [ ] Faire le front en mobile first.
- [ ] Les boutons n'ont parfois pas la même taille que les composants à côté.
- [ ] Paramètres : aligner « Enregistré » et « Tout testé ».
