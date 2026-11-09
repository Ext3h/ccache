def test_basic_compilation(ccache_test):
    source = ccache_test.workdir / "test.c"
    source.write_text("int main() {}\n")

    ccache_test.compile(["/c", "test.c", "/Fohello.obj"])
    stats_1 = ccache_test.stats()
    assert stats_1["miss"] == 1
    assert stats_1["total_hit"] == 0

    ccache_test.compile(["/c", "test.c", "/Fohello.obj"])
    stats_2 = ccache_test.stats()
    assert stats_2["miss"] == 1
    assert stats_2["total_hit"] == 1
    assert (ccache_test.workdir / "hello.obj").exists()

    ccache_test.compile(["/c", "test.c"])
    stats_2 = ccache_test.stats()
    assert stats_2["miss"] == 1
    assert stats_2["total_hit"] == 2
    assert (ccache_test.workdir / "test.obj").exists()


def test_define_change_is_miss(ccache_test):
    source = ccache_test.workdir / "test.c"
    source.write_text("int x = VALUE;\n")

    ccache_test.compile(["/c", "/DVALUE=1", "test.c"])
    stats_1 = ccache_test.stats()
    assert stats_1["miss"] == 1

    ccache_test.compile(["/c", "/DVALUE=2", "test.c"])
    stats_2 = ccache_test.stats()
    assert stats_2["miss"] == 2
    assert stats_2["total_hit"] == 0


def test_header_change_is_miss(ccache_test):
    header = ccache_test.workdir / "test.h"
    header.write_text("#define VALUE 1\n")
    source = ccache_test.workdir / "test.c"
    source.write_text('#include "test.h"\nint x = VALUE;\n')

    ccache_test.compile(["/c", "test.c"])
    stats_1 = ccache_test.stats()
    assert stats_1["miss"] == 1
    assert stats_1["total_hit"] == 0

    header.write_text("#define VALUE 2\n")
    ccache_test.compile(["/c", "test.c"])
    stats_2 = ccache_test.stats()
    assert stats_2["miss"] == 2
    assert stats_2["direct_hit"] == 0
    assert stats_2["total_hit"] == 0


def test_basedir_normalizes_paths(ccache_test):
    ccache_test.env["CCACHE_NOHASHDIR"] = "1"
    ccache_test.env["CCACHE_BASEDIR"] = str(ccache_test.workdir)

    dirs = []
    for name in ["dir1", "dir2"]:
        d = ccache_test.workdir / name
        d.mkdir()
        (d / "test.c").write_text("int x;\n")
        dirs.append(d)

    ccache_test.compile(["/c", "test.c"], cwd=dirs[0])
    stats_1 = ccache_test.stats()
    assert stats_1["miss"] == 1

    ccache_test.compile(["/c", "test.c"], cwd=dirs[1])
    stats_2 = ccache_test.stats()
    assert stats_2["miss"] == 1
    assert stats_2["total_hit"] == 1


def test_z7_with_absolute_output_hashes_cwd(ccache_test):
    # With /Z7, cl embeds the CWD in the object file, so a result must not be
    # shared between different CWDs even if the source and object file paths
    # are the same.
    source = ccache_test.workdir / "src" / "test.c"
    source.parent.mkdir()
    source.write_text("int x;\n")
    obj = ccache_test.workdir / "out" / "test.obj"
    obj.parent.mkdir()

    for i, name in enumerate(["dir1", "dir2"], start=1):
        cwd = ccache_test.workdir / name
        cwd.mkdir()
        ccache_test.compile(["/c", "/Z7", str(source), f"/Fo{obj}"], cwd=cwd)
        stats = ccache_test.stats()
        assert stats["miss"] == i
        assert stats["total_hit"] == 0
        assert str(cwd).encode() in obj.read_bytes()
