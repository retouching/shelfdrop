"""The texts of the messages of the journal, as Discord shows them, in French and in English
(rules: docs/agents/writing.md). The setting `journal.language` chooses, at each send."""

from typing import Final

from shelfdrop.journal.types import JournalTexts

FOOTER: Final = "shelfdrop"
# The name of the torrent client of an event (its fact `client`, the setting `torrent.client`);
# an event recorded before the torrent clients names qBittorrent.
CLIENTS: Final = {
    "qui": "qBittorrent",
    "qbittorrent": "qBittorrent",
    "deluge": "Deluge",
    "transmission": "Transmission",
}
DEFAULT_CLIENT: Final = "qBittorrent"

FR: Final = JournalTexts(
    titles={
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
    },
    separator=" : ",
    volumes="Tomes",
    already="Déjà présents",
    trackers="Trackers",
    size="Taille",
    type="Type",
    mode="Mode",
    modes={"auto": "Automatique", "manual": "Manuel"},
    by="Par",
    duration="Durée",
    reason="Raison",
    attempt="Essai",
    result="Résultat",
    results={"sent": "Reçu par {client}", "not_received": "Non reçu"},
    error="Erreur",
    done="Ce que shelfdrop a fait",
    country="Pays",
    refused="Connexions refusées depuis la même adresse",
    releases="Releases",
    place="À ranger dans Ranger.",
    reasons={
        "manual": "téléchargement manuel",
        "chapters": "release en chapitres",
        "no_volume": "tome introuvable",
        "unknown_author": "auteur inconnu",
        "no_files": "aucun fichier de livre",
        "missing_files": "fichiers introuvables",
        "link_refused": "lien refusé par le système de fichiers",
        "merge_failed": "fusion des MP3 en échec",
    },
    failures={
        "not_received": "{client} n'a pas reçu le torrent",
        "link_refused": "Rangement impossible",
        "merge_failed": "Fusion des MP3 en M4B impossible",
        "upload_corrupt": "Envoi corrompu",
    },
    actions={
        "not_received": "Rien d'envoyé. Réessayer depuis Téléchargements.",
        "link_refused": "Rien d'écrasé, fichiers laissés en place.",
        "merge_failed": "Rien d'écrasé, pistes MP3 laissées en place.",
        "upload_corrupt": "Fichier supprimé, à envoyer de nouveau.",
    },
    volume="T{:02d}",
    volume_range="T{:02d} à T{:02d}",
    last_join=" et ",
    gigabytes="{} Go",
    megabytes="{} Mo",
    decimal=",",
    seconds="{} s",
    minutes="{} min",
    hours="{hours} h {minutes:02d}",
    any_release="Toute release",
    chapters_from="Ch. {} et suivants",
    chapters_range="Ch. {} à {}",
)

EN: Final = JournalTexts(
    titles={
        "sent": "Sent",
        "downloaded": "Downloaded",
        "placed": "Placed",
        "to_place": "To place",
        "uploaded": "File uploaded",
        "retry": "Retry",
        "failed": "Failed",
        "misplaced": "Misplaced",
        "login": "Sign-in",
        "found": "Found",
    },
    separator=": ",
    volumes="Volumes",
    already="Already there",
    trackers="Trackers",
    size="Size",
    type="Type",
    mode="Mode",
    modes={"auto": "Automatic", "manual": "Manual"},
    by="By",
    duration="Time",
    reason="Reason",
    attempt="Attempt",
    result="Result",
    results={"sent": "Received by {client}", "not_received": "Not received"},
    error="Error",
    done="What shelfdrop did",
    country="Country",
    refused="Sign-ins refused from the same address",
    releases="Releases",
    place="Waiting in Place.",
    reasons={
        "manual": "manual download",
        "chapters": "release in chapters",
        "no_volume": "volume not found",
        "unknown_author": "unknown author",
        "no_files": "no book file",
        "missing_files": "files not found",
        "link_refused": "link refused by the file system",
        "merge_failed": "MP3 merge failed",
    },
    failures={
        "not_received": "{client} did not receive the torrent",
        "link_refused": "Placement failed",
        "merge_failed": "MP3 to M4B merge failed",
        "upload_corrupt": "Upload corrupt",
    },
    actions={
        "not_received": "Nothing sent. Retry from Downloads.",
        "link_refused": "Nothing overwritten, files left in place.",
        "merge_failed": "Nothing overwritten, MP3 tracks left in place.",
        "upload_corrupt": "File deleted, to upload again.",
    },
    volume="Vol. {:02d}",
    volume_range="Vol. {:02d} to {:02d}",
    last_join=" and ",
    gigabytes="{} GB",
    megabytes="{} MB",
    decimal=".",
    seconds="{} s",
    minutes="{} min",
    hours="{hours} h {minutes} min",
    any_release="Any release",
    chapters_from="Ch. {} onwards",
    chapters_range="Ch. {} to {}",
)


def texts_of(language: str) -> JournalTexts:
    """The texts of a language of the setting; French for any other value."""
    return EN if language == "en" else FR
