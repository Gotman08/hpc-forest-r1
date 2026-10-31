"""Real ELF interception against a synthetic NVRTC ABI, not a GPU result."""
import json
import os
import platform
import shutil
import subprocess
from pathlib import Path

import pytest

from hpc_forest import diagnostic_cuda


@pytest.mark.skipif(platform.system() != "Linux" or not shutil.which("cc"), reason="ELF and a host C compiler required")
@pytest.mark.parametrize("status", [0, 6])
def test_nvrtc_interposer_preserves_options_return_value_and_binary(tmp_path, status):
    library = tmp_path / "fake.c"
    library.write_text('''#include <stddef.h>
#include <string.h>
int nvrtcCompileProgram(void*p,int n,const char*const*o) {
 return n==2 && strcmp(o[0],"--std=c++17")==0 && strcmp(o[1],"a\\\\b\\\"c")==0 ? STATUS : 99;
}
int nvrtcGetProgramLogSize(void*p,size_t*n){*n=4;return 0;}
int nvrtcGetProgramLog(void*p,char*b){memcpy(b,"log",4);return 0;}
int nvrtcGetCUBINSize(void*p,size_t*n){*n=4;return 0;}
int nvrtcGetCUBIN(void*p,char*b){memcpy(b,"ELF!",4);return 0;}
int nvrtcGetPTXSize(void*p,size_t*n){*n=4;return 0;}
int nvrtcGetPTX(void*p,char*b){memcpy(b,"ptx",4);return 0;}
'''.replace("STATUS", str(status)))
    main = tmp_path / "main.c"
    main.write_text('''int nvrtcCompileProgram(void*,int,const char*const*);
int main(){const char*o[]={"--std=c++17","a\\\\b\\\"c"};return nvrtcCompileProgram(0,2,o);}
''')
    subprocess.run(["cc", "-shared", "-fPIC", str(library), "-o", str(tmp_path / "libfake.so")], check=True)
    subprocess.run(["cc", str(main), "-L" + str(tmp_path), "-Wl,-rpath," + str(tmp_path),
                    "-lfake", "-o", str(tmp_path / "main")], check=True)

    def run(argv, name):
        subprocess.run(argv, check=True, capture_output=True)

    directory = tmp_path / "capture"
    env = diagnostic_cuda.prepare(directory, run)
    execution = subprocess.run([str(tmp_path / "main")], env={**os.environ, **env}, check=False)
    assert execution.returncode == status
    evidence = diagnostic_cuda.evidence(directory)
    assert len(evidence["invocations"]) == 1
    record = evidence["invocations"][0]
    assert record["status"] == status and record["options"] == ["--std=c++17", 'a\\b"c']
    assert record["options_unchanged"] and record["library_sha256"]
    assert bool(evidence["binaries"]) == (status == 0)
    if status == 0:
        assert Path(evidence["binaries"][0]["path"]).read_bytes() == b"ELF!"
    assert json.loads((directory / "observer.json").read_text())["official_execution"] is False
