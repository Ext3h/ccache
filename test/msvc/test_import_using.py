import json
import os
import shutil
import time

import pytest

IDL = """import "oaidl.idl";
[uuid(8C7B4A6E-1D2F-4E3A-9B5C-6D7E8F901234), version(1.0)]
library TestLib {
  [uuid(8C7B4A6E-1D2F-4E3A-9B5C-6D7E8F901235), object, oleautomation]
  interface ITest : IUnknown { HRESULT %s([out, retval] long* r); };
};
"""


def test_import_type_library_change_is_not_a_hit(ccache_test):
    if not shutil.which("midl"):
        pytest.skip("midl not found in PATH")

    (ccache_test.workdir / "test.cpp").write_text(
        '#import "test.tlb" raw_interfaces_only\n'
        "int f(TestLib::ITest* p) { return p != nullptr; }\n"
    )

    def build_type_library(method):
        (ccache_test.workdir / "test.idl").write_text(IDL % method)
        ccache_test.run(["midl", "/nologo", "/tlb", "test.tlb", "test.idl"])

    build_type_library("Alpha")
    # Let cl generate test.tlh before ccache's invocation so that ccache doesn't
    # treat it as an input file modified during the compilation.
    ccache_test.run(["cl", "/nologo", "/c", "test.cpp"])

    ccache_test.compile(["/c", "test.cpp"])
    stats_1 = ccache_test.stats()
    assert stats_1["miss"] == 1
    assert stats_1["total_hit"] == 0

    ccache_test.compile(["/c", "test.cpp"])
    stats_2 = ccache_test.stats()
    assert stats_2["total_hit"] == 1

    build_type_library("Beta")
    # cl regenerates test.tlh only if test.tlb is newer; make sure it is.
    past = time.time() - 100
    os.utime(ccache_test.workdir / "test.tlh", (past, past))
    ccache_test.compile(["/c", "test.cpp"])
    stats_3 = ccache_test.stats()
    assert stats_3["total_hit"] == 1
    assert stats_3["direct_hit"] == 0
    assert "Beta" in (ccache_test.workdir / "test.tlh").read_text()


def test_using_directive_is_unsupported(ccache_test):
    (ccache_test.workdir / "lib.cpp").write_text(
        "public ref class Foo { public: literal int X = 1; };\n"
    )
    result = ccache_test.run(
        ["cl", "/nologo", "/clr", "/LD", "lib.cpp"], check=False
    )
    if result.returncode != 0:
        pytest.skip("cl /clr not available")

    (ccache_test.workdir / "test.cpp").write_text(
        '#using "lib.dll"\nint f() { return Foo::X; }\n'
    )
    for _ in range(2):
        ccache_test.compile(["/clr", "/c", "test.cpp"])

    stats = json.loads(
        ccache_test.run(
            [ccache_test.ccache_exe, "--print-stats", "--format", "json"]
        ).stdout
    )
    assert stats.get("cache_miss", 0) == 0
    assert stats.get("direct_cache_hit", 0) == 0
    assert stats.get("preprocessed_cache_hit", 0) == 0
    assert stats.get("unsupported_code_directive", 0) == 2
