#!/usr/bin/env python3
"""
NxNative GitHub Actions disk guard.

Commands:
  preclean <runner_temp>   Remove only stale NxNative-owned temp folders.
  patch <repo>              Patch dmsh_build.py and build_ipa_from_nsp.py for CI-safe cleanup.
  start                    Start detached disk monitor (environment variables configure paths).
  stop                     Stop monitor and write a final report.
  report                   Print the last 200 lines of the monitor log.

Environment:
  RUNNER_TEMP, GITHUB_WORKSPACE, HOME
  NX_GAME_DIR              e.g. $RUNNER_TEMP/GameFiles
  NX_PROGRESS_LOG          build console log captured with tee
  NX_MONITOR_LOG           optional monitor log path
  NX_MONITOR_INTERVAL      default 30 seconds
  NX_MONITOR_DEEP_INTERVAL default 300 seconds
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path


MARKER_DM = "# NX_CI_DISK_GUARD_TEMP_CLEANUP"
MARKER_IPA = "# NX_CI_DISK_GUARD_POST_SHADER_CLEANUP"


def say(s: str) -> None:
    print(s, flush=True)


def du_k(path: Path, timeout: int = 120) -> str:
    if not path.exists():
        return "missing"
    try:
        p = subprocess.run(
            ["du", "-sk", str(path)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
        return p.stdout.strip().replace("\t", " KB  ", 1) or f"du exit={p.returncode}"
    except Exception as e:
        return f"du error: {e}"


def preclean(runner_temp: Path) -> None:
    """Delete only the two uniquely named temp roots owned by this workflow."""
    for name in ("GameFiles", "nxnative"):
        p = runner_temp / name
        if p.exists():
            say(f"[preclean] before: {du_k(p)}")
            shutil.rmtree(p)
            say(f"[preclean] removed stale workflow directory: {p}")
    for name in ("disk-monitor.log", "disk-monitor.pid", "disk-monitor.reserve"):
        p = runner_temp / name
        try:
            p.unlink()
        except FileNotFoundError:
            pass
    say("[preclean] after: " + du_k(runner_temp))
    say("[preclean] no Homebrew, Xcode, Runner _diag, /private/tmp, or user-wide caches were deleted.")


def patch_dmsh_build(repo: Path) -> bool:
    p = repo / "dm/gfx/tools/dmsh_build.py"
    if not p.is_file():
        raise RuntimeError(f"dmsh_build.py not found: {p}")
    src = p.read_text(encoding="utf-8")

    if MARKER_DM in src:
        say("[patch] dmsh_build.py already patched")
        return False

    # Once all translator processes have returned, their input .bin files and
    # the batch job_*.json descriptors are dead. Keep .spv/.res.json until each
    # shader has completed finish().
    anchor = "def fin(key):"
    if src.count(anchor) != 1:
        raise RuntimeError(
            f"Expected exactly one {anchor!r} in {p}; found {src.count(anchor)}. "
            "No source changes were made."
        )

    pre_fin = (
        f"{MARKER_DM}\n"
        "# All XLATE worker processes have returned at this point. Their .bin\n"
        "# inputs and job_*.json batch descriptors are no longer read.\n"
        "for _ci_name in os.listdir(w):\n"
        "    if _ci_name.endswith('.bin') or (_ci_name.startswith('job_') and _ci_name.endswith('.json')):\n"
        "        try: os.unlink(os.path.join(w, _ci_name))\n"
        "        except OSError: pass\n"
        "\n"
    )
    src = src.replace(anchor, pre_fin + anchor, 1)

    # Skip the per-shader CAS publication in this ephemeral CI build. The
    # Metal-source-keyed CAS/metallib and variant caches remain enabled while
    # the current compilation is running.
    line_re = re.compile(
        r"(?m)^    if result\[1\] == 'ok': publish_cache\(key, digests\[key\], rule_fps\[key\], CODE_FP\)\s*$"
    )
    if len(line_re.findall(src)) != 1:
        raise RuntimeError(
            f"Expected exactly one successful-shader publish_cache line in {p}; "
            "no safe per-shader cleanup patch was completed."
        )

    replacement = (
        "    if result[1] == 'ok':\n"
        "        if os.environ.get('DMSH_DISABLE_SHADER_CAS') != '1':\n"
        "            publish_cache(key, digests[key], rule_fps[key], CODE_FP)\n"
        "        # finish() has copied the final MSL/reflection/library to out/IOSOUT,\n"
        "        # compiled the iOS library, and completed vin/fetch processing.\n"
        "        # A paired vertex shader reads its pixel partner from out/, not w/.\n"
        "        for _ci_name in os.listdir(w):\n"
        "            if _ci_name.startswith(key + '.') or _ci_name.startswith(key + '_'):\n"
        "                _ci_path = os.path.join(w, _ci_name)\n"
        "                if os.path.isfile(_ci_path):\n"
        "                    try: os.unlink(_ci_path)\n"
        "                    except OSError: pass\n"
        "        try: os.unlink(os.path.join(w, f'job1_{key}.json'))\n"
        "        except OSError: pass"
    )
    src = line_re.sub(lambda _: replacement, src, count=1)
    p.write_text(src, encoding="utf-8")
    say("[patch] dmsh_build.py: release consumed translator files and per-shader intermediates")
    say("[patch] dmsh_build.py: DMSH_DISABLE_SHADER_CAS=1 can skip the redundant per-shader CAS copies")
    return True


def patch_ipa_builder(repo: Path) -> bool:
    p = repo / "scripts/build_ipa_from_nsp.py"
    if not p.is_file():
        raise RuntimeError(f"build_ipa_from_nsp.py not found: {p}")
    src = p.read_text(encoding="utf-8")

    if MARKER_IPA in src:
        say("[patch] build_ipa_from_nsp.py already patched")
        return False

    # Both the pinned BC fallback revision and current standard main have one
    # NVN call assigning the iOS shader directory to `ios`. It is deliberately
    # placed after build_shaders() returns: regression checks, c1/cb tables and
    # chain pruning have already completed; build_ipa.sh consumes MSL_IOS only.
    lines = src.splitlines(keepends=True)
    matches = [i for i, line in enumerate(lines) if re.search(r"^\s*ios\s*=\s*build_shaders\(", line)]
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected exactly one NVN `ios = build_shaders(...)` call in {p}; "
            f"found {len(matches)}. No post-shader cleanup was added."
        )

    i = matches[0]
    indent = re.match(r"^\s*", lines[i]).group(0)
    block = (
        f"{indent}{MARKER_IPA}\n"
        f"{indent}# The NVN shader step has returned successfully. Its Mac-side\n"
        f"{indent}# outputs/CAS and the Switch shader package are no longer inputs\n"
        f"{indent}# to the iOS packer. Keep shader/ios (the IPA's MSL_IOS input).\n"
        f"{indent}if os.environ.get('NX_CI_RELEASE_SHADER_SPACE') == '1':\n"
        f"{indent}    for _ci_path in (sh / 'pkg', sh / 'cache'):\n"
        f"{indent}        if _ci_path.is_dir():\n"
        f"{indent}            say(f'[CI disk guard] removing consumed shader data: {{_ci_path}}')\n"
        f"{indent}            shutil.rmtree(_ci_path)\n"
    )
    lines.insert(i + 1, block)
    p.write_text("".join(lines), encoding="utf-8")
    say("[patch] build_ipa_from_nsp.py: after successful NVN shader build, remove shader/pkg and shader/cache")
    say("[patch] shader/ios is deliberately retained for IPA packaging")
    return True


def patch(repo: Path) -> None:
    a = patch_dmsh_build(repo)
    b = patch_ipa_builder(repo)
    say(f"[patch] complete: dmsh_build={'changed' if a else 'already patched'}, "
        f"IPA builder={'changed' if b else 'already patched'}")


def run_cmd(args: list[str], timeout: int = 120) -> str:
    try:
        p = subprocess.run(
            args, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=timeout, check=False
        )
        return p.stdout.strip()
    except Exception as e:
        return f"[command error] {' '.join(args)}: {e}"


def monitor_log_path() -> Path:
    return Path(os.environ.get(
        "NX_MONITOR_LOG",
        str(Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "disk-monitor.log")
    ))


def progress_state() -> str:
    p = os.environ.get("NX_PROGRESS_LOG")
    if not p or not Path(p).is_file():
        return "progress log not available yet"
    try:
        data = Path(p).read_bytes()[-65536:].decode("utf-8", errors="replace")
        found = re.findall(
            r"\[\d+/\d+\]\s+([^\r\n]{1,160})",
            data
        )
        return found[-1].strip() if found else "stage not parsed"
    except Exception as e:
        return f"progress read error: {e}"


def free_kb() -> int | None:
    out = run_cmd(["df", "-k", "/"])
    rows = out.splitlines()
    if len(rows) >= 2:
        cols = rows[-1].split()
        try:
            return int(cols[3])
        except Exception:
            return None
    return None


def write_log(log: Path, text: str) -> None:
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8", errors="replace") as f:
        f.write(text.rstrip() + "\n")
        f.flush()
        try:
            os.fsync(f.fileno())
        except OSError:
            pass


def monitored_paths() -> list[tuple[str, Path]]:
    runner_temp = Path(os.environ.get("RUNNER_TEMP", "/tmp"))
    home = Path(os.environ.get("HOME", str(Path.home())))
    workspace = Path(os.environ.get("GITHUB_WORKSPACE", ""))
    game = Path(os.environ.get("NX_GAME_DIR", str(runner_temp / "GameFiles")))
    runner_root = Path("/Users/runner/actions-runner")
    return [
        ("RUNNER_TEMP", runner_temp),
        ("GameFiles", game),
        ("nxnative-download-work", runner_temp / "nxnative"),
        ("GITHUB_WORKSPACE", workspace),
        ("Xcode DerivedData (home)", home / "Library/Developer/Xcode/DerivedData"),
        ("Xcode Archives (home)", home / "Library/Developer/Xcode/Archives"),
        ("Home Library Caches", home / "Library/Caches"),
        ("private_tmp", Path("/private/tmp")),
        ("actions-runner", runner_root),
        ("actions-runner cached", runner_root / "cached"),
        ("actions-runner diagnostics", runner_root / "cached/_diag"),
    ]


def find_build_roots(game_dir: Path) -> list[Path]:
    try:
        return sorted(p for p in game_dir.glob("*_build") if p.is_dir())
    except OSError:
        return []


def snapshot(log: Path, deep: bool = False, reason: str = "periodic") -> None:
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    rows = [
        "",
        "=" * 88,
        f"[{now}] SNAPSHOT reason={reason} deep={deep}",
        "[progress] " + progress_state(),
        "[df -h /]",
        run_cmd(["df", "-h", "/"]),
        "[df -i /]",
        run_cmd(["df", "-i", "/"]),
    ]
    free = free_kb()
    if free is not None:
        rows.append(f"[free] {free / 1024 / 1024:.2f} GiB")

    if deep:
        for label, path in monitored_paths():
            if path.exists():
                rows.append(f"[du] {label}: {du_k(path)}")
            else:
                rows.append(f"[du] {label}: missing ({path})")

        for build in find_build_roots(Path(os.environ.get("NX_GAME_DIR", "/tmp/GameFiles"))):
            rows.append(f"[build-root] {build}")
            for rel in (
                "extract", "aoc", "tools", "tmp", "shader/pkg",
                "shader/cache", "shader/ios", "logs", "xcode-derived-data", "ipa"
            ):
                p = build / rel
                if p.exists():
                    rows.append(f"[build-subdir] {rel}: {du_k(p)}")
            for p in sorted(build.glob("patched_*")):
                if p.is_dir():
                    rows.append(f"[build-subdir] {p.name}: {du_k(p)}")

            tmp = build / "tmp"
            if tmp.exists():
                dmsh_dirs = sorted(p for p in tmp.glob("dmsh_*") if p.is_dir())
                for d in dmsh_dirs:
                    rows.append(f"[dmsh-temp] {d}: {du_k(d)}")
                    counts: dict[str, int] = {}
                    sizes: dict[str, int] = {}
                    for root, _, files in os.walk(d):
                        for name in files:
                            ext = Path(name).suffix.lower() or "<no-ext>"
                            counts[ext] = counts.get(ext, 0) + 1
                            try:
                                sizes[ext] = sizes.get(ext, 0) + (Path(root) / name).stat().st_size
                            except OSError:
                                pass
                    for ext in sorted(counts):
                        rows.append(
                            f"[dmsh-files] {ext}: count={counts[ext]} "
                            f"size={sizes.get(ext, 0) / 1024 / 1024:.1f} MiB"
                        )

            for rel in ("shader", "tmp", "xcode-derived-data"):
                p = build / rel
                if p.exists():
                    rows.append(f"[deep-du] {rel}:")
                    out = run_cmd(["du", "-k", "-d", "3", str(p)], timeout=240)
                    lines = out.splitlines()
                    try:
                        lines.sort(key=lambda s: int(s.split()[0]), reverse=True)
                    except Exception:
                        pass
                    rows.extend("  " + x for x in lines[:50])

            rows.append("[largest files >100MiB in build folder]")
            out = run_cmd([
                "find", str(build), "-type", "f", "-size", "+100M",
                "-exec", "stat", "-f", "%z %N", "{}", ";"
            ], timeout=240)
            files = out.splitlines()
            try:
                files.sort(key=lambda s: int(s.split(" ", 1)[0]), reverse=True)
            except Exception:
                pass
            rows.extend("  " + x for x in files[:40])
    else:
        rows.append("[quick] directory size scan deferred to the 5-minute deep snapshot")

    if deep:
        rows.append("[diskutil apfs list]")
        rows.append(run_cmd(["diskutil", "apfs", "list"], timeout=120))
        rows.append("[top processes: PID PPID RSS %CPU COMMAND]")
        rows.append(run_cmd([
            "bash", "-lc",
            "ps -Ao pid,ppid,rss,%cpu,command | sort -nrk4 | head -25"
        ], timeout=60))
        rows.append("[deleted-but-open files]")
        rows.append(run_cmd(["bash", "-lc", "lsof +L1 2>/dev/null | head -80"], timeout=90))

    write_log(log, "\n".join(rows))


def monitor_loop(log: Path, pidfile: Path) -> None:
    interval = int(os.environ.get("NX_MONITOR_INTERVAL", "30"))
    deep_interval = int(os.environ.get("NX_MONITOR_DEEP_INTERVAL", "300"))
    reserve = Path(os.environ.get(
        "NX_RESERVE_FILE",
        str(Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "disk-monitor.reserve")
    ))
    last_deep = 0.0
    stopping = False

    def stop_handler(_sig, _frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop_handler)
    signal.signal(signal.SIGINT, stop_handler)
    write_log(log, f"[monitor] started pid={os.getpid()} interval={interval}s")
    while not stopping:
        free = free_kb()
        # Release the preallocated emergency space before the volume is full,
        # so the monitor and Actions Runner still have room to flush logs.
        if free is not None and free <= 8 * 1024 * 1024 and reserve.exists():
            try:
                reserve.unlink()
                write_log(log, "[EMERGENCY] free space <= 8 GiB: released 256 MiB reserve")
            except OSError as e:
                write_log(log, f"[EMERGENCY] could not release reserve: {e}")

        now = time.time()
        deep = now - last_deep >= deep_interval
        try:
            snapshot(log, deep=deep, reason="periodic")
            if deep:
                last_deep = now
        except Exception as e:
            try:
                write_log(log, f"[monitor-error] {type(e).__name__}: {e}")
            except OSError:
                pass
        for _ in range(interval):
            if stopping:
                break
            time.sleep(1)

    try:
        snapshot(log, deep=True, reason="monitor-stop")
    except Exception as e:
        try:
            write_log(log, f"[final-snapshot-error] {e}")
        except OSError:
            pass
    try:
        pidfile.unlink()
    except OSError:
        pass
    write_log(log, "[monitor] stopped")


def start_monitor() -> None:
    runner_temp = Path(os.environ.get("RUNNER_TEMP", "/tmp"))
    log = monitor_log_path()
    pidfile = runner_temp / "disk-monitor.pid"
    reserve = runner_temp / "disk-monitor.reserve"
    if pidfile.exists():
        say(f"[monitor] PID file already exists: {pidfile}")
        return

    # Allocate a real 256 MiB emergency reserve (not a sparse truncate).
    if not reserve.exists():
        try:
            with reserve.open("wb") as f:
                block = b"\0" * (1024 * 1024)
                for _ in range(256):
                    f.write(block)
                f.flush()
                os.fsync(f.fileno())
            say(f"[monitor] allocated emergency reserve: {reserve}")
        except OSError as e:
            say(f"[monitor] reserve allocation skipped: {e}")

    env = os.environ.copy()
    env["NX_MONITOR_LOG"] = str(log)
    script = str(Path(__file__).resolve())
    with log.open("a", encoding="utf-8") as out:
        proc = subprocess.Popen(
            [sys.executable, script, "monitor"],
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=subprocess.STDOUT,
            env=env,
            start_new_session=True,
            close_fds=True,
        )
    pidfile.write_text(str(proc.pid), encoding="ascii")
    say(f"[monitor] started pid={proc.pid}; log={log}")


def stop_monitor() -> None:
    runner_temp = Path(os.environ.get("RUNNER_TEMP", "/tmp"))
    log = monitor_log_path()
    pidfile = runner_temp / "disk-monitor.pid"
    reserve = runner_temp / "disk-monitor.reserve"
    if pidfile.exists():
        try:
            pid = int(pidfile.read_text().strip())
            os.kill(pid, signal.SIGTERM)
            say(f"[monitor] sent SIGTERM to {pid}")
        except ProcessLookupError:
            say("[monitor] process already exited")
        except Exception as e:
            say(f"[monitor] stop warning: {e}")
        for _ in range(15):
            if not pidfile.exists():
                break
            time.sleep(1)
    else:
        say("[monitor] PID file not found; monitor may have been killed with the runner")
    if reserve.exists():
        try:
            reserve.unlink()
            say("[monitor] released remaining emergency reserve")
        except OSError as e:
            say(f"[monitor] could not remove reserve: {e}")
    if log.exists():
        say("[monitor] final log tail:")
        try:
            lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
            for line in lines[-200:]:
                print(line)
        except OSError as e:
            say(f"[monitor] cannot read log: {e}")


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("preclean")
    p.add_argument("runner_temp", type=Path)
    p = sub.add_parser("patch")
    p.add_argument("repo", type=Path)
    sub.add_parser("start")
    sub.add_parser("monitor")
    sub.add_parser("stop")
    sub.add_parser("report")
    args = ap.parse_args()

    if args.cmd == "preclean":
        preclean(args.runner_temp)
    elif args.cmd == "patch":
        patch(args.repo)
    elif args.cmd == "start":
        start_monitor()
    elif args.cmd == "monitor":
        monitor_loop(
            monitor_log_path(),
            Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "disk-monitor.pid",
        )
    elif args.cmd == "stop":
        stop_monitor()
    elif args.cmd == "report":
        log = monitor_log_path()
        if log.exists():
            print("\n".join(log.read_text(encoding="utf-8", errors="replace").splitlines()[-200:]))
        else:
            say(f"No monitor log at {log}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
