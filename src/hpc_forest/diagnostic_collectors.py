"""Extensible, shell-free profiler plans for an already authorized workload.

Adapters describe native evidence, never a speedup or an official score. New
adapters must implement discovery, typed options, bounded collection and units.
"""
from __future__ import annotations

import csv
import io
import math
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Collector:
    tools: tuple[str, ...]
    platforms: tuple[str, ...]
    scope: str
    units: str
    limitations: str
    reference: str


COLLECTORS = {
    "runtime": Collector((), (), "Whole fixed workload", "seconds (wall clock)",
        "Diagnostic elapsed time includes launch and instrumentation overhead; not an official sample.", ""),
    "perf-stat": Collector(("perf",), ("Linux",), "Local process and inherited children",
        "Native event units; enabled/running percentage accompanies multiplexed counters",
        "PMU permissions and architecture constrain events. Remote MPI ranks are not local children.",
        "https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/tools/perf/Documentation/perf-stat.txt"),
    "perf-record": Collector(("perf",), ("Linux",), "Sampled local stacks, symbols and annotated instructions",
        "Samples and event periods; report percentages are not elapsed seconds",
        "Unwinding, debug symbols, sampling skid and lost samples limit line attribution.",
        "https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/tools/perf/Documentation/perf-record.txt"),
    "hpctoolkit": Collector(("hpcrun", "hpcstruct", "hpcprof"), ("Linux",),
        "Calling contexts, threads and MPI ranks; CPU/GPU events selected from hpcrun -L",
        "Native HPCToolkit event units and sampling periods",
        "OMPT, MPI and GPU support depend on this build/runtime. Database needs HPCViewer for graphical exploration.",
        "https://hpctoolkit.org/documentation.html"),
    "nsys": Collector(("nsys",), ("Linux",), "CPU/GPU timeline, CUDA API, transfers, synchronization, MPI/NVTX",
        "Native trace timestamps and statistics units (typically ns); percentages use report-specific denominators",
        "Tracing perturbs timing; CPU sampling disabled by default. Multi-rank output is per rank.",
        "https://docs.nvidia.com/nsight-systems/UserGuide/index.html"),
    "ncu": Collector(("ncu",), ("Linux",), "Selected NVIDIA CUDA kernels, source/SASS and device metrics",
        "Metric-specific units emitted by ncu; retain metric name, unit and replay context",
        "Requires counter permission and supported GPU. Replay/cache control perturb execution; no end-to-end timing.",
        "https://docs.nvidia.com/nsight-compute/NsightComputeCli/index.html"),
    "compiler": Collector((), ("Linux", "Darwin"), "Intercepted compiler invocations, optimization reports and intermediate files",
        "Compiler remarks, not time measurements",
        "PATH wrappers cannot intercept absolute compiler paths or cached objects. CUDA-kernel diagnostics also capture dynamic NVRTC output without changing its options. Coverage is explicit; remarks are not causal proof.",
        "https://gcc.gnu.org/onlinedocs/gcc/Developer-Options.html"),
    "disassembly": Collector(("objdump",), (), "Binary machine instructions, symbols, source and line mapping",
        "Addresses/instructions, not dynamic costs",
        "CUDA-kernel diagnostics use cuobjdump on captured NVRTC CUBIN, not the host launcher. Source mapping requires debug information; optimized code can map ambiguously.",
        "https://sourceware.org/binutils/docs/binutils/objdump.html"),
    "scorep": Collector(("scorep", "scorep-info"), ("Linux",), "Instrumented MPI/OpenMP/hybrid profile or trace",
        "Native CUBE/OTF2 units and event definitions",
        "Requires diagnostic rebuild via intercepted compilers and matching MPI/OpenMP adapters; overhead can be large.",
        "https://perftools.pages.jsc.fz-juelich.de/cicd/scorep/tags/latest/html/scoreptools.html"),
    "scalasca": Collector(("scorep", "scorep-info", "scalasca"), ("Linux",),
        "Score-P trace analysis of MPI/OpenMP waits and communication",
        "Native CUBE/OTF2 units; distinguish wait-state attribution from causation",
        "Requires a compatible instrumented MPI build and existing allocation; never submits another job.",
        "https://www.scalasca.org/software/scalasca-2.x/documentation.html"),
}

PROBES = {
    "perf": ("--version",), "hpcrun": ("--version",), "hpcstruct": ("--version",),
    "hpcprof": ("--version",), "nsys": ("--version",), "ncu": ("--version",),
    "objdump": ("--version",), "scorep": ("--version",), "scorep-info": ("config-summary",),
    "cuobjdump": ("--version",), "nvdisasm": ("--version",),
    "scalasca": ("--version",), "nvidia-smi": ("--query-gpu=name,driver_version,compute_cap", "--format=csv"),
}
DETAIL_PROBES = {
    "perf": ("list", "--raw-dump"), "hpcrun": ("-L",),
    "nsys": ("status", "--environment"), "ncu": ("--query-metrics",),
    "scorep-info": ("config-summary",),
}


def options_for(collector, options):
    if collector not in COLLECTORS:
        raise ValueError("Unknown collector")
    options = options or {}
    keys = {"perf-stat": {"events"}, "perf-record": {"event", "frequency", "symbol"},
            "hpctoolkit": {"events", "trace"}, "nsys": {"trace"},
            "ncu": {"kernel", "metrics", "launch_count", "launch_skip"},
            "scorep": {"trace"}, "scalasca": set()}.get(collector, set())
    if not isinstance(options, dict) or set(options) - keys:
        raise ValueError("Unknown collector options")
    for key in {"events", "metrics"} & options.keys():
        if (not isinstance(options[key], list) or not 1 <= len(options[key]) <= 16
                or any(not isinstance(s, str) or not re.fullmatch(r"[A-Za-z0-9_.:=/-]{1,160}", s)
                       or s.startswith("-") for s in options[key])):
            raise ValueError("Invalid event/metric names")
    for key in {"event", "symbol", "kernel"} & options.keys():
        if (not isinstance(options[key], str) or not 1 <= len(options[key]) <= 240
                or options[key].startswith("-") or any(ord(c) < 32 for c in options[key])):
            raise ValueError("Invalid collector filter")
    for key, lo, hi in (("frequency", 1, 1000), ("launch_count", 1, 20), ("launch_skip", 0, 100000)):
        if key in options and (type(options[key]) is not int or not lo <= options[key] <= hi):
            raise ValueError("Invalid collector limit")
    if "trace" in options:
        if collector == "nsys":
            if (not isinstance(options["trace"], list) or not options["trace"]
                    or any(t not in {"cuda", "nvtx", "osrt", "mpi", "openmp"} for t in options["trace"])):
                raise ValueError("Unsupported Nsight trace domain")
        elif type(options["trace"]) is not bool:
            raise ValueError("trace must be boolean")
    return options


def launch_parts(workload):
    """Separate a recognized MPI launcher from its rank command, including scripts.

    A program/bundle path occurring as an argument is not a command boundary.
    Unknown launcher syntax needs an adapter rather than guessed instrumentation.
    """
    launchers = {"srun", "mpirun", "mpiexec", "mpiexec.hydra", "orterun"}
    if not workload:
        raise ValueError("Empty diagnostic workload")
    if Path(workload[0]).name not in launchers:
        if any(Path(arg).name in launchers for arg in workload[1:]):
            raise ValueError("Wrapped MPI launcher requires an explicit workload adapter")
        return [], workload
    if ":" in workload:
        raise ValueError("MPMD launcher requires an explicit workload adapter")
    valued = {"-n", "-np", "--np", "--ntasks", "-N", "--nodes", "-c", "--cpus-per-task",
              "--ntasks-per-node", "--gpus-per-task", "--gpus-per-node", "--cpu-bind", "--gpu-bind",
              "--mpi", "--map-by", "--bind-to", "--rank-by", "--host", "-host", "--hostfile",
              "-hostfile", "--machinefile", "-machinefile", "--wdir", "-wdir", "--chdir", "-D",
              "--export", "-x", "--kill-on-bad-exit"}
    flags = {"--overcommit", "--exclusive", "--overlap", "--unbuffered", "--label", "-l",
             "--tag-output", "--timestamp-output", "--report-bindings", "--oversubscribe",
             "--use-hwthread-cpus", "--allow-run-as-root"}
    index = 1
    while index < len(workload):
        arg = workload[index]
        if arg == "--":
            index += 1
            break
        if not arg.startswith("-"):
            break
        option, equal, value = arg.partition("=")
        if option in flags and not equal:
            index += 1
        elif option in valued and equal and value:
            index += 1
        elif option in valued and not equal and index + 1 < len(workload):
            index += 2
        elif re.fullmatch(r"-(?:np|n|N|c)\d+", arg):
            index += 1
        else:
            raise ValueError("Unsupported MPI launcher option; an explicit workload adapter is required")
    if index >= len(workload):
        raise ValueError("MPI launcher has no rank command")
    return workload[:index], workload[index:]


def collect(collector, options, workload, binary, output, run, tools):
    """Run typed commands using an injected bounded executor. No arbitrary CLI flags."""
    options = options_for(collector, options)
    app = list(workload)
    # Instrument the whole wrapper, or each rank after a recognized MPI launcher.
    launcher, rank = launch_parts(app) if collector in {"hpctoolkit", "nsys", "ncu"} else ([], app)
    def command(name, args, *, env=None):
        return run([tools.get(args[0], args[0]), *map(str, args[1:])], name, env=env)
    def per_rank(prefix):
        return [*launcher, *prefix, *rank]
    if collector == "runtime":
        command("runtime", app)
    elif collector == "perf-stat":
        command("perf-stat", ["perf", "stat", "-x", ";", "-o", output / "counters.csv",
                              "-e", ",".join(options.get("events", ["task-clock", "cycles", "instructions"])), "--", *app])
    elif collector == "perf-record":
        command("perf-record", ["perf", "record", "-o", output / "perf.data", "-g", "--call-graph", "dwarf",
                                "-F", options.get("frequency", 99), "-e", options.get("event", "cpu-clock"), "--", *app])
        command("perf-report", ["perf", "report", "--stdio", "--header", "-i", output / "perf.data"])
        args = ["perf", "annotate", "--stdio", "-i", output / "perf.data"]
        if options.get("symbol"):
            args += ["--symbol", options["symbol"]]
        command("perf-annotate", args)
    elif collector == "hpctoolkit":
        measurement = output / "hpctoolkit-measurements"
        prefix = [tools["hpcrun"], "-o", str(measurement)]
        for event in options.get("events", ["CPUTIME"]):
            prefix += ["-e", event]
        if options.get("trace"):
            prefix.append("-t")
        command("hpcrun", per_rank(prefix))
        command("hpcstruct", ["hpcstruct", "-j", "1", measurement])
        command("hpcprof", ["hpcprof", "-o", output / "hpctoolkit-database", measurement])
    elif collector == "nsys":
        report = output / ("timeline-%q{SLURM_PROCID}-%p" if launcher else "timeline")
        command("nsys-profile", per_rank([tools["nsys"], "profile", "--sample=none", "--cpuctxsw=none",
            "--trace=" + ",".join(options.get("trace", ["cuda", "nvtx", "osrt"])),
            "--force-overwrite=false", "--output=" + str(report)]))
        for number, path in enumerate(sorted(output.glob("*.nsys-rep"))):
            command(f"nsys-stats-{number}", ["nsys", "stats", "--format", "csv", path])
            # stats exports SQLite beside the report. Retain it for structured
            # timeline reads; don't flatten correlations into a single top-N list.
            if not path.with_suffix(".sqlite").exists():
                command(f"nsys-export-{number}", ["nsys", "export", "--type", "sqlite",
                    "--output", path.with_suffix(".sqlite"), path])
        if not list(output.glob("*.nsys-rep")):
            raise ValueError("Nsight Systems produced no report")
    elif collector == "ncu":
        if launcher:
            raise ValueError("Concurrent MPI kernel replay is not enabled; requires a separately authorized rank workload")
        prefix = ["ncu", "--target-processes", "all", "--clock-control", "none", "--cache-control", "none",
                  "--launch-count", options.get("launch_count", 1), "--launch-skip", options.get("launch_skip", 0),
                  "--export", output / "kernels", "--import-source", "yes"]
        if options.get("kernel"):
            prefix += ["--kernel-name", options["kernel"]]
        prefix += ["--metrics", ",".join(options["metrics"])] if options.get("metrics") else ["--set", "basic"]
        command("ncu-profile", [*prefix, *app])
        command("ncu-metrics", ["ncu", "--import", output / "kernels.ncu-rep", "--page", "raw", "--csv"])
        command("ncu-source", ["ncu", "--import", output / "kernels.ncu-rep", "--page", "source", "--print-source", "cuda,sass"])
    elif collector == "disassembly":
        command("disassembly", ["objdump", "-d", "-S", "-l", "-C", binary])
        command("binary-headers", ["objdump", "-p", binary])
    elif collector in {"scorep", "scalasca"}:
        env = {"SCOREP_EXPERIMENT_DIRECTORY": str(output / "scorep-measurement"),
               "SCOREP_ENABLE_PROFILING": "true", "SCOREP_ENABLE_TRACING":
                   "true" if options.get("trace") or collector == "scalasca" else "false",
               "SCOREP_TOTAL_MEMORY": "32M"}
        if collector == "scalasca":
            command("scalasca", ["scalasca", "-analyze", "-t", "-e", output / "scorep-measurement", *app], env=env)
        else:
            command("scorep-measurement", app, env=env)
    elif collector != "compiler":
        raise ValueError("Collector has no implementation")


def perf_counters(path):
    """Keep unsupported/not-counted values null, with their literal reason and units."""
    result = []
    if not path.exists():
        return result
    for row in csv.reader(io.StringIO(path.read_text(errors="replace")), delimiter=";"):
        if len(row) < 3 or row[0].startswith("#"):
            continue
        try:
            number = float(row[0].strip())
            number = number if math.isfinite(number) else None
        except ValueError:
            number = None
        result.append({"value": number, "unit": row[1].strip(), "event": row[2].strip(),
                       "unavailable_reason": row[0].strip() if number is None else None,
                       "runtime_ns": row[3].strip() if len(row) > 3 else None,
                       "running_percent": row[4].strip() if len(row) > 4 else None,
                       "raw_fields": row})
    return result
