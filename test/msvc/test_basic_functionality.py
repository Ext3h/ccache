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


def test_basedir_keeps_stdout_lines_without_path(ccache_test):
    ccache_test.env["CCACHE_BASEDIR"] = str(ccache_test.workdir)
    source = ccache_test.workdir / "test.cpp"
    source.write_text(
        "template <typename T> int f(T t) { return t; }\n"
        "int g() { return f(1.5); }\n"
    )
    cl_args = ["/nologo", "/c", "/W4", "test.cpp"]

    expected = ccache_test.run(["cl", *cl_args]).stdout
    # cl echoes the source file name and continues the warning with "with",
    # "[", "T=double" and "]" lines, none of which start with a path.
    assert expected.startswith("test.cpp\n")
    assert "T=double" in expected

    result_1 = ccache_test.compile(cl_args)
    assert ccache_test.stats()["miss"] == 1
    assert result_1.stdout == expected

    result_2 = ccache_test.compile(cl_args)
    assert ccache_test.stats()["total_hit"] == 1
    assert result_2.stdout == expected
