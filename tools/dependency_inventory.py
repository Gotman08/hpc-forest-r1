"""Record the installed dependency closure for the supported web/dev profile.

Linux markers can be resolved from the Windows metadata, but installation on
Linux still requires its own CI evidence. No dependency is downloaded here.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as metadata
import json
import tomllib
from pathlib import Path

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


def inventory(root: Path, platform: str):
    configuration = tomllib.loads((root / "pyproject.toml").read_text())
    project = configuration["project"]
    pending = [*project["dependencies"], *project["optional-dependencies"]["web"],
               *project["optional-dependencies"]["dev"], *configuration["build-system"]["requires"]]
    environment = default_environment()
    if platform == "linux":
        environment.update(sys_platform="linux", platform_system="Linux", os_name="posix",
                           python_version="3.12", python_full_version="3.12.0")
    selected, visited = {}, set()
    while pending:
        requirement = Requirement(pending.pop())
        name = canonicalize_name(requirement.name)
        if requirement.marker and not requirement.marker.evaluate({**environment, "extra": ""}):
            continue
        distribution = metadata.distribution(name)
        if distribution.version not in requirement.specifier:
            raise ValueError(f"Installed {name}=={distribution.version} violates {requirement}")
        licenses = []
        for file in distribution.files or []:
            if ".dist-info/" in str(file) and any(part.lower().startswith(("license", "copying", "notice")) for part in file.parts):
                content = distribution.locate_file(file).read_bytes()
                licenses.append({"path": str(file), "sha256": hashlib.sha256(content).hexdigest()})
        selected[name] = {"version": distribution.version,
                          "license": distribution.metadata.get("License-Expression") or
                              (distribution.metadata.get("License") or "Not declared in metadata").splitlines()[0],
                          "license_files": licenses}
        for extra in {"", *requirement.extras}:
            if (name, extra) in visited:
                continue
            visited.add((name, extra))
            for raw in distribution.requires or []:
                child = Requirement(raw)
                if not child.marker or child.marker.evaluate({**environment, "extra": extra}):
                    child.marker = None
                    pending.append(str(child))
    return dict(sorted(selected.items()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=["windows", "linux"], required=True)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    args = parser.parse_args()
    result = inventory(Path(__file__).resolve().parents[1], args.platform)
    args.lock.write_text("# Exact web/dev dependency versions, no TabPFN; generated from installed metadata.\n"
                        + "# Revalidation is required on the target platform; see docs/DISTRIBUTION.md.\n"
                        + "".join(f"{name}=={item['version']}\n" for name, item in result.items()), encoding="utf-8", newline="\n")
    args.inventory.write_text(json.dumps({"platform": args.platform, "packages": result}, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"Recorded {len(result)} packages for {args.platform}")


if __name__ == "__main__":
    main()
