# TODO

Retours sur la 0.10.0 en production (22/10/2026).

## Bugs

- [ ] `GET /api/v1/library/series/<id>` répond 503.
- [ ] La fenêtre de la fiche d'une série a un double scroll.
- [ ] La recherche ne doit pas partir quand la barre de recherche est vide.
- [ ] Quand on quitte la page de recherche puis qu'on y revient, ne pas garder la recherche précédente, ou alors la garder sans la relancer.

## Fonctionnalités

- [ ] Ajouter les couvertures sur les titres envoyés automatiquement.
- [ ] Une page par section, où seule la vue change, pour avoir un vrai historique de navigation (retour / avance du navigateur, liens directs).
- [ ] Catégories des indexeurs :
  - retirer le filtre sur le nom des releases (`cbz`, etc.) s'il existe ;
  - si ce n'est pas déjà le cas, prendre les trackers depuis les indexeurs réels de Prowlarr, sans filtre ;
  - pouvoir choisir sur le site, pour chaque indexeur, la ou les catégories à utiliser et à quel type elles correspondent (par exemple Nyaa : « Literature » pour les mangas). Une ou plusieurs catégories par type.
- [ ] Servir la vraie doc d'API générée par FastAPI (Swagger UI / ReDoc depuis l'OpenAPI) à la place de la page actuelle de `/api/docs`.

## Interface

- [ ] Faire le front en mobile first.
- [ ] Les boutons n'ont parfois pas la même taille que les composants à côté.
- [ ] Paramètres : aligner « Enregistré » et « Tout testé ».
