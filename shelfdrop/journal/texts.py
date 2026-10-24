"""The French texts of the messages of the journal, as Discord shows them (rules:
docs/agents/writing.md)."""

from typing import Final

from shelfdrop.journal.types import EventType

TITLES: Final[dict[EventType, str]] = {
    "sent": "Envoyé",
    "downloaded": "Téléchargé",
    "placed": "Rangé",
    "to_place": "À associer",
    "uploaded": "Fichier envoyé",
    "retry": "Réessai",
    "failed": "Échec",
    "misplaced": "Mal rangés",
    "login": "Connexion",
    "found": "Trouvé",
}
FOOTER: Final = "shelfdrop"
VOLUMES: Final = "Tomes"
ALREADY: Final = "Déjà présents"
TRACKERS: Final = "Trackers"
SIZE: Final = "Taille"
TYPE: Final = "Type"
MODE: Final = "Mode"
MODES: Final = {"auto": "Automatique", "manual": "Manuel"}
BY: Final = "Par"
DURATION: Final = "Durée"
DESTINATION: Final = "Destination"
REASON: Final = "Raison"
ATTEMPT: Final = "Essai"
RESULT: Final = "Résultat"
# The name of the torrent client of an event (its fact `client`, the setting `torrent.client`);
# an event recorded before the torrent clients names qBittorrent.
CLIENTS: Final = {
    "qui": "qBittorrent",
    "qbittorrent": "qBittorrent",
    "deluge": "Deluge",
    "transmission": "Transmission",
}
DEFAULT_CLIENT: Final = "qBittorrent"
# `{client}`: the name of the torrent client.
RESULTS: Final = {"sent": "Reçu par {client}", "not_received": "Non reçu"}
ERROR: Final = "Erreur"
DONE: Final = "Ce que shelfdrop a fait"
ACCOUNT: Final = "Compte"
COUNTRY: Final = "Pays"
REFUSED: Final = "Connexions refusées depuis la même adresse"
RELEASES: Final = "Releases"
PLACE: Final = "À ranger dans Ranger."
# Why a download was not placed alone: the Ranger page takes it.
REASONS: Final = {
    "manual": "téléchargement manuel",
    "chapters": "release en chapitres",
    "no_volume": "tome introuvable",
    "unknown_author": "auteur inconnu",
    "no_files": "aucun fichier de livre",
    "missing_files": "fichiers introuvables",
    "link_refused": "lien refusé par le système de fichiers",
    "merge_failed": "fusion des MP3 en échec",
}
# What failed, and what shelfdrop did then (`{client}`: the name of the torrent client).
FAILURES: Final = {
    "not_received": "{client} n'a pas reçu le torrent",
    "link_refused": "Rangement impossible",
    "merge_failed": "Fusion des MP3 en M4B impossible",
    "upload_corrupt": "Envoi corrompu",
}
ACTIONS: Final = {
    "not_received": "Rien d'envoyé. Réessayer depuis Téléchargements.",
    "link_refused": "Rien d'écrasé, fichiers laissés en place.",
    "merge_failed": "Rien d'écrasé, pistes MP3 laissées en place.",
    "upload_corrupt": "Fichier supprimé, à envoyer de nouveau.",
}
