from shelfdrop.uploads.types import MIB, chunk_count, chunk_length


def test_a_file_is_cut_in_chunks_of_50_mib_the_last_one_the_rest() -> None:
    size = 120 * MIB + 3

    assert chunk_count(size, 50 * MIB) == 3
    assert [chunk_length(size, 50 * MIB, i) for i in range(3)] == [50 * MIB, 50 * MIB, 20 * MIB + 3]
    assert chunk_count(50 * MIB, 50 * MIB) == 1
    assert chunk_count(1, 50 * MIB) == 1
