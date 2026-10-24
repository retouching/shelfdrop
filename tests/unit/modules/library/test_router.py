"""shelfdrop.modules.library.router: the name of a file downloaded."""

from shelfdrop.modules.library.router import attachment


def test_a_file_name_goes_in_ascii_and_whole_in_utf8() -> None:
    assert attachment("Berserk - T01.cbz") == (
        "attachment; filename=\"Berserk - T01.cbz\"; filename*=UTF-8''Berserk%20-%20T01.cbz"
    )
    assert attachment('L\'Été "x"\r\n.epub') == (
        'attachment; filename="L\'_t_ _x___.epub"; '
        "filename*=UTF-8''L%27%C3%89t%C3%A9%20%22x%22%0D%0A.epub"
    )
    assert attachment("") == "attachment; filename=\"file\"; filename*=UTF-8''"
