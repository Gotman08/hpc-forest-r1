"""Regression checks for generic I/O plumbing; no contest problem solutions."""

import json
import shutil
import struct
import subprocess
import sys
from pathlib import Path

import pytest

from hpc_forest import contracts as c


def case(name="sample", value=None):
    return {
        "name": name,
        "argv": [],
        "stdin": value or {"text": "abc\n"},
        "files": [],
        "capture_files": [],
    }


def contract():
    sample = case()
    return {
        "language": "c",
        "source_files": ["echo.c"],
        "compiler_flags": ["-O2"],
        "comparison": {
            "mode": "auto",
            "abs_tol": 0,
            "rel_tol": 0,
            "basis_quote": "",
            "binary_format": "",
        },
        "search_cases": [sample, case("same-input")],
        "confirmation_cases": [sample],
        "benchmark_case": sample,
    }


def official(tmp_path):
    root = tmp_path / "official"
    root.mkdir()
    (root / "echo.c").write_text("/* synthetic fixture, not a benchmark */")
    (root / "echo.h").write_text("/* synthetic header */")
    return root


def test_binary_bytes_roundtrip_and_mismatch():
    data = b"\x00\xff\xfe\x80\x01"
    assert c.unblob(c.blob(data)) == data
    assert c.equal_output({"stdout": c.blob(data)}, {"stdout": c.blob(data)}, {"mode": "auto"})
    assert not c.equal_output(
        {"stdout": c.blob(data)}, {"stdout": c.blob(data[:-1])}, {"mode": "auto"}
    )


def test_corrupt_expected_blob_is_infrastructure_failure():
    value = c.blob(b"original")
    value["base64"] = c.blob(b"wrong")["base64"]
    with pytest.raises(RuntimeError):
        c.unblob(value)


def test_timed_out_sanitizer_cannot_silently_validate_a_candidate(tmp_path):
    (tmp_path / "stdin.data").write_bytes(b"")
    stalled = {"name": "bounded probe", "files": [], "stdin": "stdin.data",
               "argv": ["-c", "import time; time.sleep(60)"]}
    with pytest.raises(RuntimeError, match="correctness remains unverified"):
        c.probe_sanitizer(sys.executable, stalled, timeout=0.02, resources=tmp_path)


def test_text_and_numeric_binary_comparison():
    options = {"mode": "text", "abs_tol": 1e-6, "rel_tol": 0}
    assert c.compare_bytes(b"1.0000000\nlabel", b"1.0000001 label\n", options)
    assert not c.compare_bytes(b"1 label", b"1 other", options)
    options.update(mode="binary_numeric", binary_format="<f")
    expected = struct.pack("<ff", 1.0, 2.0)
    assert c.compare_bytes(expected, struct.pack("<ff", 1.0000001, 2.0), options)
    assert not c.compare_bytes(expected, struct.pack("<ff", 9.0, 2.0), options)
    assert not c.compare_bytes(expected, expected[:-1], options)


def test_existing_header_is_not_reported_missing(tmp_path):
    root = official(tmp_path)
    config = contract()
    config["source_files"].append("echo.h")
    units, warnings = c.validate_contract(config, root)
    assert units == ["echo.c"]
    assert warnings[0]["code"] == "header_is_include"


def test_missing_input_identifies_field_and_available_files(tmp_path):
    root = official(tmp_path)
    config = contract()
    config["search_cases"][0]["stdin"] = {"official_file": "invented.in"}
    with pytest.raises(c.ContractError) as error:
        c.validate_contract(config, root)
    assert error.value.diagnostic["code"] == "missing_input"
    assert error.value.diagnostic["value"] == "invented.in"
    assert "echo.c" in error.value.diagnostic["available_files"]


@pytest.mark.parametrize("name", ["../escape", "/absolute", "C:/absolute", "a\\b", "."])
def test_paths_stay_inside_experiment(name):
    with pytest.raises(c.ContractError):
        c.relative(name)


def test_tolerance_needs_official_quote_and_padding_cannot_hide_values(tmp_path):
    root = official(tmp_path)
    config = contract()
    config["comparison"]["abs_tol"] = 1e-5
    with pytest.raises(c.ContractError, match="unsupported_tolerance"):
        c.validate_contract(config, root)
    config["comparison"].update(abs_tol=0, mode="binary_numeric", binary_format="<4x")
    with pytest.raises(c.ContractError, match="binary_format"):
        c.validate_contract(config, root)


def test_model_generator_can_emit_binary_and_fixture_paths_are_portable(tmp_path):
    resources = tmp_path / "validation"
    sample = case(value={"python": "import sys\nsys.stdout.buffer.write(bytes([0,255,128,10]))\n"})
    resolved = c.materialize(sample, tmp_path, resources / "fixtures/sample", resources)
    assert not Path(resolved["stdin"]).is_absolute()
    assert (resources / resolved["stdin"]).read_bytes() == b"\x00\xff\x80\n"


def test_shared_cases_do_not_block_and_binary_checker_rejects_wrong_program(tmp_path):
    gcc = shutil.which("gcc")
    if not gcc:
        pytest.skip("gcc is unavailable")
    root = official(tmp_path)
    # Pure byte-copy fixture exercises the I/O adapter, not a contest algorithm.
    (root / "echo.c").write_text(
        "#include <stdio.h>\nint main(void){int c;while((c=getchar())!=EOF)putchar(c);return 0;}\n"
    )
    config = contract()
    sample = case(value={"python": "import sys\nsys.stdout.buffer.write(bytes([255,0,128,42]))\n"})
    config.update(
        search_cases=[sample, {**sample, "name": "duplicate"}],
        confirmation_cases=[sample],
        benchmark_case=sample,
    )
    receipt = c.prepare(config, root, tmp_path / "prepared", probe_timeout=5)
    trusted = Path(receipt["validation"])
    frozen = json.loads((trusted / "contract.json").read_text())
    assert receipt["search_cases"] == 1
    assert receipt["coverage"]["independent_input_sets"] is False
    assert any(w["code"] == "duplicate_case_collapsed" for w in receipt["warnings"])
    binary = tmp_path / "prepared/reference-build/solution"
    if sys.platform == "win32":
        binary = binary.with_suffix(".exe") if binary.with_suffix(".exe").exists() else binary
    result = subprocess.run(
        [sys.executable, str(trusted / "contract_tool.py"), "check", str(binary), "search"],
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["correct"] is True
    wrong = tmp_path / "wrong.c"
    wrong.write_text('#include <stdio.h>\nint main(void){puts("WRONG");return 0;}\n')
    bad = tmp_path / "bad"
    subprocess.run([gcc, str(wrong), "-o", str(bad)], check=True)
    bad = (
        bad.with_suffix(".exe")
        if sys.platform == "win32" and bad.with_suffix(".exe").exists()
        else bad
    )
    result = subprocess.run(
        [sys.executable, str(trusted / "contract_tool.py"), "check", str(bad), "search"],
        capture_output=True,
    )
    assert result.returncode == 1
    assert json.loads(result.stdout)["correct"] is False
    assert all(
        frozen["search"][0]["expected"][key]["base64"] for key in frozen["search"][0]["expected"]
    )


@pytest.mark.parametrize("language,compiler,filename", [("c", "gcc", "echo.c"), ("c++", "g++", "echo.cpp")])
def test_frozen_build_rejects_uninitialized_openmp_reduction(
    tmp_path, monkeypatch, language, compiler, filename
):
    if not shutil.which(compiler):
        pytest.skip(f"{compiler} is unavailable")
    monkeypatch.setenv("OMP_NUM_THREADS", "2")
    root = tmp_path / "official"
    root.mkdir()
    # A counter fixture exercises compiler diagnostics, not any contest algorithm.
    program = (
        "#include <stdio.h>\nint main(void) { int counter = 0;\n"
        "#pragma omp parallel for reduction(+:counter)\n"
        "for (int i=0; i<4; ++i) counter += 1;\n"
        'printf("%d\\n", counter); return counter != 4; }\n'
    )
    (root / filename).write_text(program)
    config = contract()
    config.update(
        language=language,
        source_files=[filename],
        compiler_flags=[
            "-O3", "-fopenmp", "-Werror=uninitialized", "-Werror=maybe-uninitialized"
        ],
    )
    receipt = c.prepare(config, root, tmp_path / "prepared", probe_timeout=5)
    trusted = Path(receipt["validation"])
    candidate = tmp_path / "candidate"
    (candidate / "src").mkdir(parents=True)
    (candidate / "src" / filename).write_text(program.replace("counter = 0", "counter"))
    result = subprocess.run(
        [sys.executable, str(trusted / "contract_tool.py"), "build", str(candidate), str(tmp_path / "build")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    diagnostic = json.loads(result.stderr)["diagnostic"]
    assert diagnostic["code"] == "compilation_failed"
    assert "uninitialized" in diagnostic["stderr"]
    assert not (tmp_path / "build/solution").exists()


def test_mismatch_diagnostic_reports_index_counts_and_nan_without_leaking_oracle():
    exp = {"stdout": c.blob(b"10 20 30.5 40\n")}
    act_val = {"stdout": c.blob(b"10 20 99.0 40\n")}
    diag = c.mismatch_diagnostic(exp, act_val, {"mode": "text"})
    assert diag["kind"] == "token_value_mismatch"
    assert diag["expected_tokens"] == 4 and diag["actual_tokens"] == 4
    assert diag["first_mismatch_token"] == 2
    assert diag["non_finite_actual"] is False
    assert "30.5" not in json.dumps(diag)

    act_nan = {"stdout": c.blob(b"10 nan 30.5\n")}
    diag_nan = c.mismatch_diagnostic(exp, act_nan, {"mode": "text"})
    assert diag_nan["kind"] == "token_count_mismatch"
    assert diag_nan["first_mismatch_token"] == 1
    assert diag_nan["non_finite_actual"] is True

    diag_empty = c.mismatch_diagnostic(exp, {"stdout": c.blob(b"")}, {"mode": "auto"})
    assert diag_empty["kind"] == "empty_output" and diag_empty["actual_bytes"] == 0

    bin_cmp = {"mode": "binary_numeric", "binary_format": "<ff"}
    exp_bin = {"stdout": c.blob(struct.pack("<ffff", 1.0, 2.0, 3.0, 4.0))}
    act_bin = {"stdout": c.blob(struct.pack("<ffff", 1.0, 2.0, 3.0, float("nan")))}
    diag_bin = c.mismatch_diagnostic(exp_bin, act_bin, bin_cmp)
    assert diag_bin["kind"] == "numeric_record_mismatch"
    assert diag_bin["first_mismatch_record"] == 1 and diag_bin["first_mismatch_field"] == 1
    assert diag_bin["non_finite_actual"] is True


def test_sanitizer_probe_rejects_undefined_behavior_on_smallest_search_case(tmp_path):
    if not shutil.which("gcc"):
        pytest.skip("gcc is unavailable")
    root = official(tmp_path)
    (root / "echo.c").write_text(
        "#include <stdio.h>\nint main(void){int c;while((c=getchar())!=EOF)putchar(c);return 0;}\n"
    )
    receipt = c.prepare(contract(), root, tmp_path / "prepared", probe_timeout=5)
    trusted = Path(receipt["validation"])
    candidate = tmp_path / "candidate"
    (candidate / "src").mkdir(parents=True)
    # Candidate outputs the exact expected characters but triggers signed overflow / OOB UB.
    (candidate / "src/echo.c").write_text(
        "#include <stdio.h>\n"
        "int main(void){\n"
        "  volatile int x = 0x7fffffff;\n"
        "  volatile int y = x + 1;\n"
        "  (void)y;\n"
        "  int c; while((c=getchar())!=EOF) putchar(c);\n"
        "  return 0;\n"
        "}\n"
    )
    build_dir = tmp_path / "build"
    build_res = subprocess.run(
        [sys.executable, str(trusted / "contract_tool.py"), "build", str(candidate), str(build_dir)],
        capture_output=True,
        text=True,
    )
    assert build_res.returncode == 0, build_res.stderr
    assert c.sanitizer_executable_path(build_dir).is_file()
    check_res = subprocess.run(
        [
            sys.executable,
            str(trusted / "contract_tool.py"),
            "check",
            str(c.executable_path(build_dir)),
            "search",
        ],
        capture_output=True,
        text=True,
    )
    assert check_res.returncode == 1
    assert json.loads(check_res.stderr)["diagnostic"]["code"] == "sanitizer_failed"



