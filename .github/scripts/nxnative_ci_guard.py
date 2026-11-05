#!/usr/bin/env python3
"""
NxNative GitHub Actions disk guard.

Commands:
  preclean <runner_temp>   Remove only stale NxNative-owned temp folders.
  patch <repo>              Patch shader build cleanup without shortening dmsh_build.py intermediate lifetimes.
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


MARKER_DM = "# NX_CI_DISK_GUARD_SAFE_CAS"
LEGACY_MARKER_DM = "# NX_CI_DISK_GUARD_TEMP_CLEANUP"
MARKER_IPA = "# NX_CI_DISK_GUARD_POST_SHADER_CLEANUP"
MARKER_ROMFS_MAIN = "# NX_CI_DISK_GUARD_RELEASE_ROMFS_AFTER_SPLIT"
MARKER_ROMFS_SH = "# NX_CI_DISK_GUARD_SKIP_MISSING_ROMFS_VALIDATION"
MARKER_UE_IOSTORE = "# NX_CI_UE_IOSTORE_SHADER_DECODE"


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
    """Apply only the safe CAS toggle; never delete translator intermediates early.

    dmsh_build.geometry_finish()/finish() can still read a shader's .bin,
    .spv and reflection files while fin(key) is running. The upstream builder
    removes the whole temporary directory only after every fin() task finishes.
    Keep that lifetime unchanged.
    """
    p = repo / "dm/gfx/tools/dmsh_build.py"
    if not p.is_file():
        raise RuntimeError(f"dmsh_build.py not found: {p}")
    src = p.read_text(encoding="utf-8")

    # Upgrade checkouts that were patched by the previous, unsafe version of
    # this guard. Remove its pre-fin .bin/job cleanup block.
    legacy_pre_fin = re.compile(
        r"(?ms)^# NX_CI_DISK_GUARD_TEMP_CLEANUP\n"
        r"# All XLATE worker processes have returned at this point\. Their \.bin\n"
        r"# inputs and job_\*\.json batch descriptors are no longer read\.\n"
        r"for _ci_name in os\.listdir\(w\):\n"
        r"    if _ci_name\.endswith\('\.bin'\) or \(_ci_name\.startswith\('job_'\) and _ci_name\.endswith\('\.json'\)\):\n"
        r"        try: os\.unlink\(os\.path\.join\(w, _ci_name\)\)\n"
        r"        except OSError: pass\n\n"
        r"(?=def fin\(key\):)"
    )
    src, removed_pre_fin = legacy_pre_fin.subn("", src)

    # Remove the previous per-shader cleanup, which could race paired shader
    # finishing and geometry_finish(). Restore the original one-line publish.
    legacy_per_shader = re.compile(
        r"(?m)^    if result\[1\] == 'ok':\n"
        r"        if os\.environ\.get\('DMSH_DISABLE_SHADER_CAS'\) != '1':\n"
        r"            publish_cache\(key, digests\[key\], rule_fps\[key\], CODE_FP\)\n"
        r"        # finish\(\) has copied the final MSL/reflection/library to out/,\n"
        r"        # compiled the iOS library, and completed vin/fetch processing\.\n"
        r"        # A paired vertex shader reads its pixel partner from out/, not w/\.\n"
        r"        for _ci_name in os\.listdir\(w\):\n"
        r"            if _ci_name\.startswith\(key \+ '\.'\) or _ci_name\.startswith\(key \+ '_'\):\n"
        r"                _ci_path = os\.path\.join\(w, _ci_name\)\n"
        r"                if os\.path\.isfile\(_ci_path\):\n"
        r"                    try: os\.unlink\(_ci_path\)\n"
        r"                    except OSError: pass\n"
        r"        try: os\.unlink\(os\.path\.join\(w, f'job1_\{key\}\.json'\)\)\n"
        r"        except OSError: pass$"
    )
    src, removed_per_shader = legacy_per_shader.subn(
        "    if result[1] == 'ok': publish_cache(key, digests[key], rule_fps[key], CODE_FP)",
        src,
    )

    if MARKER_DM in src:
        say("[patch] dmsh_build.py already has the safe CAS-only patch")
        return bool(removed_pre_fin or removed_per_shader)

    if LEGACY_MARKER_DM in src:
        raise RuntimeError(
            f"Found an unrecognized legacy cleanup patch in {p}. Refusing to modify it; "
            "inspect the marked block before proceeding."
        )

    anchor = "    if result[1] == 'ok': publish_cache(key, digests[key], rule_fps[key], CODE_FP)"
    if src.count(anchor) != 1:
        raise RuntimeError(
            f"Expected exactly one successful-shader publish_cache line in {p}; "
            f"found {src.count(anchor)}. No unsafe cleanup was added."
        )

    replacement = (
        f"    {MARKER_DM}\n"
        "    if result[1] == 'ok':\n"
        "        if os.environ.get('DMSH_DISABLE_SHADER_CAS') != '1':\n"
        "            publish_cache(key, digests[key], rule_fps[key], CODE_FP)"
    )
    src = src.replace(anchor, replacement, 1)
    p.write_text(src, encoding="utf-8")
    say("[patch] dmsh_build.py: CAS publication can be disabled for ephemeral CI builds")
    say("[patch] dmsh_build.py: .bin/.spv/.res.json/job files are retained until upstream fin() tasks finish")
    say("[patch] dmsh_build.py: upstream shutil.rmtree(w) remains the only translator-temp cleanup")
    return True



def patch_profile_guess(repo: Path) -> bool:
    """Include IoStore shader-library containers in the UE shader-decode trigger.

    UE5 games can keep ShaderCodeLibrary data in .utoc/.ucas without a pak
    shader archive. build_sources() previously counted only Unreal paks, so
    ue_decode stayed false and decode_ue_shaders() never ran for those games.
    """
    p = repo / "dm/games/profile_guess.py"
    if not p.is_file():
        raise RuntimeError(f"profile_guess.py not found: {p}")
    src = p.read_text(encoding="utf-8")
    if MARKER_UE_IOSTORE in src:
        say("[patch] profile_guess.py already detects IoStore shader libraries")
        return False

    signature = (
        "def shader_sources(imports, glsl_src, glslc_mods, spirv, unreal_paks, "
        "trinity_packs=0, legacy_paks=0, gl_names=0, gl_src=0, gl_files=0, "
        "oodle_pkz=0, nro_imports=frozenset(), oodle_gfpak=0, oodle_ue3=0, "
        "frostbite=False, romfs_glsl=0):"
    )
    new_signature = signature[:-2] + ", io_shader_libraries=0):"
    old_ue_decode = (
        "'ue_decode': (not vulkan and not gl and bool(unreal_paks), "
        "f'{unreal_paks} Unreal pak(s): the shaders are Oodle-compressed in their "
        "shader code archives (Octopath Traveler 0), decoded by booting the game on the Mac'),"
    )
    new_ue_decode = (
        "'ue_decode': (not vulkan and not gl and bool(unreal_paks or io_shader_libraries), "
        "f'{unreal_paks} Unreal pak(s), {io_shader_libraries} IoStore shader library "
        "container(s): decode Unreal shader archives in the UE shader-decode step'),"
    )
    import_anchor = (
        "    sys.path.insert(0, str(HERE.parent / 'gfx/tools')); import uepak\n"
    )
    import_replacement = (
        import_anchor
        + "    " + MARKER_UE_IOSTORE + "\n"
        + "    io_shader_libraries = len(uepak.io_shader_tocs(str(romfs)))\n"
    )
    call_anchor = (
        "frostbite=frostbite.is_frostbite(str(romfs)), romfs_glsl=romfs_glsl)"
    )
    call_replacement = (
        "frostbite=frostbite.is_frostbite(str(romfs)), "
        "romfs_glsl=romfs_glsl, io_shader_libraries=io_shader_libraries)"
    )

    for label, old in (
        ("shader_sources signature", signature),
        ("UE decode decision", old_ue_decode),
        ("uepak import", import_anchor),
        ("shader_sources call", call_anchor),
    ):
        count = src.count(old)
        if count != 1:
            raise RuntimeError(
                f"Expected exactly one {label} anchor in {p}; found {count}. "
                "Refusing to apply a partial IoStore patch."
            )

    src = src.replace(signature, new_signature, 1)
    src = src.replace(old_ue_decode, new_ue_decode, 1)
    src = src.replace(import_anchor, import_replacement, 1)
    src = src.replace(call_anchor, call_replacement, 1)
    p.write_text(src, encoding="utf-8")
    say("[patch] profile_guess.py: IoStore ShaderCodeLibrary containers now trigger UE shader decode")
    return True

def patch_ipa_builder(repo: Path) -> bool:
    """Patch the standard NxNative builder for post-split RomFS release.

    RomFS is released only after split_shaders() has returned successfully,
    only for NVN games, and only when --romfs separate is selected. The
    extracted control data/icon remain available to build_ipa.sh.
    """
    p = repo / "scripts/build_ipa_from_nsp.py"
    if not p.is_file():
        raise RuntimeError(f"build_ipa_from_nsp.py not found: {p}")
    src = p.read_text(encoding="utf-8")
    changed = False

    # Only the newer upstream builder has image-backed RomFS and --romfs separate.
    # The BC fallback checkout is older and keeps a directory-based RomFS bundled.
    supports_separate = (
        "romfs_mode = args.romfs or ROMFS" in src
        and "import romfs as rfs" in src
    )
    if MARKER_ROMFS_MAIN not in src and supports_separate:
        anchor = "        if observed_glslc is not None: check_glslc_coverage(observed_glslc, g)\n"
        if src.count(anchor) != 1:
            raise RuntimeError(
                "Could not find the unique post-split/pre-Metal anchor in "
                f"{p}; no RomFS handoff patch was applied."
            )
        block = (
            f"        {MARKER_ROMFS_MAIN}\n"
            "        # First pass stops after shader split; the workflow uploads RomFS.img,\n"
            "        # then reruns this builder to reuse extraction/rewrite/split caches.\n"
            "        if (romfs_mode == 'separate' and gfx == 'nvn'\n"
            "                and (os.environ.get('NX_CI_STOP_AFTER_SPLIT') == '1'\n"
            "                     or os.environ.get('NX_CI_RELEASE_ROMFS') == '1')):\n"
            "            _ci_candidates = [dirs[_ci_version] for _ci_version in sv] + [game]\n"
            "            _ci_seen_romfs = set()\n"
            "            _ci_images = []\n"
            "            for _ci_dir in _ci_candidates:\n"
            "                _ci_image = Path(rfs.source(_ci_dir)).resolve()\n"
            "                if _ci_image in _ci_seen_romfs:\n"
            "                    continue\n"
            "                _ci_seen_romfs.add(_ci_image)\n"
            "                try:\n"
            "                    _ci_image.relative_to(work.resolve())\n"
            "                except ValueError:\n"
            "                    raise BuildError(f'refusing to release RomFS outside the build folder: {_ci_image}')\n"
            "                if _ci_image.is_file():\n"
            "                    _ci_images.append((_ci_image, _ci_image.stat().st_size))\n"
            "            if os.environ.get('NX_CI_STOP_AFTER_SPLIT') == '1':\n"
            "                if not _ci_images:\n"
            "                    raise BuildError('NVN separate-ROMFS build produced no standalone RomFS.img to upload')\n"
            "                _ci_handoff_value = os.environ.get('NX_CI_ROMFS_HANDOFF_DIR')\n"
            "                if not _ci_handoff_value:\n"
            "                    raise BuildError('NX_CI_ROMFS_HANDOFF_DIR is required for the pre-Metal upload pass')\n"
            "                _ci_handoff = Path(_ci_handoff_value).resolve()\n"
            "                _ci_handoff.mkdir(parents=True, exist_ok=True)\n"
            "                _ci_main_image = Path(rfs.source(game)).resolve()\n"
            "                if not _ci_main_image.is_file():\n"
            "                    raise BuildError(f'packed game RomFS image is missing: {_ci_main_image}')\n"
            "                _ci_artifact_image = _ci_handoff / 'RomFS.img'\n"
            "                if _ci_artifact_image.exists():\n"
            "                    _ci_artifact_image.unlink()\n"
            "                os.link(_ci_main_image, _ci_artifact_image)\n"
            "                (_ci_handoff / 'ready').write_text('RomFS.img ready\\n', encoding='utf-8')\n"
            "                say(f'[CI disk guard] shader split complete; RomFS ready for upload: {_ci_main_image} ({_ci_main_image.stat().st_size / 2**30:.2f} GiB)')\n"
            "                say('[CI disk guard] stopping before Metal; the next workflow step uploads RomFS.img')\n"
            "                raise SystemExit(0)\n"
            "            if os.environ.get('NX_CI_RELEASE_ROMFS') == '1':\n"
            "                if not _ci_images:\n"
            "                    raise BuildError('no standalone RomFS.img found on the post-upload Metal pass')\n"
            "                for _ci_image, _ci_size in _ci_images:\n"
            "                    if not _ci_image.is_file() or _ci_image.stat().st_size != _ci_size:\n"
            "                        raise BuildError(f'RomFS image changed or disappeared before release: {_ci_image}')\n"
            "                    _ci_free_before = shutil.disk_usage(_ci_image.parent).free\n"
            "                    _ci_image.unlink()\n"
            "                    _ci_free_after = shutil.disk_usage(_ci_image.parent).free\n"
            "                    _ci_delta = _ci_free_after - _ci_free_before\n"
            "                    say(f'[CI disk guard] removed RomFS after successful Artifact upload: {_ci_image} ({_ci_size / 2**30:.2f} GiB)')\n"
            "                    say(f'[CI disk guard] disk free: {_ci_free_before / 2**30:.2f} -> {_ci_free_after / 2**30:.2f} GiB; actual increase: {_ci_delta / 2**30:+.2f} GiB')\n"
        )
        src = src.replace(anchor, anchor + block, 1)
        changed = True
        say("[patch] build_ipa_from_nsp.py: pause after NVN shader split for workflow-managed RomFS upload")
    elif not supports_separate:
        say("[patch] upstream builder has no image-backed --romfs separate mode; skipping RomFS release patch")

    # Keep the existing post-Metal cleanup of consumed Switch-side shader data.
    if MARKER_IPA not in src:
        lines = src.splitlines(keepends=True)
        matches = [
            i for i, line in enumerate(lines)
            if re.search(r"^\s*ios\s*=\s*build_shaders\(", line)
        ]
        if len(matches) != 1:
            raise RuntimeError(
                f"Expected exactly one NVN `ios = build_shaders(...)` call in {p}; "
                f"found {len(matches)}. No post-shader cleanup was added."
            )
        i = matches[0]
        indent = re.match(r"^\s*", lines[i]).group(0)
        block = (
            f"{indent}{MARKER_IPA}\n"
            f"{indent}# Metal build has returned successfully. Keep shader/ios for IPA packing.\n"
            f"{indent}if os.environ.get('NX_CI_RELEASE_SHADER_SPACE') == '1':\n"
            f"{indent}    for _ci_path in (sh / 'pkg', sh / 'cache'):\n"
            f"{indent}        if _ci_path.is_dir():\n"
            f"{indent}            say(f'[CI disk guard] removing consumed shader data: {{_ci_path}}')\n"
            f"{indent}            shutil.rmtree(_ci_path)\n"
        )
        lines.insert(i + 1, block)
        src = "".join(lines)
        changed = True
        say("[patch] build_ipa_from_nsp.py: retain shader/ios; remove shader/pkg and shader/cache after Metal")

    # Avoid printing a push command for a path deliberately released after upload.
    if supports_separate and "NX_CI_DISK_GUARD_ROMFS_PUSH_NOTICE" not in src:
        push_anchor = "    say('the game files are not in this build. Copy them to the phone once, with the app installed (it is needed again only when the image changed, a new game version or another extraction):')\n"
        if src.count(push_anchor) != 1:
            raise RuntimeError(f"Could not find the unique say_push_romfs() notice in {p}.")
        push_block = (
            "    # NX_CI_DISK_GUARD_ROMFS_PUSH_NOTICE\n"
            "    if not os.path.isfile(image):\n"
            "        say('RomFS image is not present on this runner (released after shader split). Supply the matching RomFS.img separately; no push command can be printed here.')\n"
            "        return\n"
        )
        src = src.replace(push_anchor, push_block + push_anchor, 1)
        changed = True
        say("[patch] build_ipa_from_nsp.py: avoid printing a push_romfs command for a deleted image")

    if changed:
        p.write_text(src, encoding="utf-8")
    else:
        say("[patch] build_ipa_from_nsp.py already has all requested patches")
    return changed


def patch_build_ipa_sh(repo: Path) -> bool:
    """Allow --romfs separate IPA builds when the image was released post-split.

    The original marker validation remains mandatory whenever the image exists,
    or whenever RomFS is bundled. Only a missing image with DM_COPY_ROMFS=NO
    bypasses the check; in that case build_ipa.sh naturally omits romfs.id.
    """
    p = repo / "dm/ios/tools/build_ipa.sh"
    if not p.is_file():
        raise RuntimeError(f"build_ipa.sh not found: {p}")
    src = p.read_text(encoding="utf-8")

    if MARKER_ROMFS_SH in src:
        say("[patch] build_ipa.sh already has the missing-RomFS separate-mode patch")
        return False

    anchor = 'python3 "$DM/tools/romfs.py" "$ROMFS" "$MARKER" || die "no RomFS at $ROMFS (missing $MARKER)"'
    if src.count(anchor) != 1:
        if "DM_COPY_ROMFS" not in src:
            say("[patch] build_ipa.sh has no separate-ROMFS mode; skipping missing-image validation patch")
            return False
        raise RuntimeError(
            f"Expected exactly one RomFS marker validation in {p}; found {src.count(anchor)}. "
            "Refusing to weaken validation."
        )

    replacement = (
        f"{MARKER_ROMFS_SH}\n"
        'if [ "${DM_COPY_ROMFS:-YES}" = NO ] && [ ! -f "$ROMFS" ]; then\n'
        '  t "RomFS image was released after shader split; skipping image marker validation (separate mode)"\n'
        '  t "no romfs.id will be embedded; the matching complete RomFS.img must be supplied separately"\n'
        "else\n"
        f"  {anchor}\n"
        "fi"
    )
    src = src.replace(anchor, replacement, 1)
    p.write_text(src, encoding="utf-8")
    say("[patch] build_ipa.sh: skip RomFS marker validation only when separate mode has no image")
    say("[patch] build_ipa.sh: normal validation and romfs.id generation remain enabled when the image exists")
    return True

def patch(repo: Path) -> None:
    a = patch_dmsh_build(repo)
    ue = patch_profile_guess(repo)
    b = patch_ipa_builder(repo)
    c = patch_build_ipa_sh(repo)
    say(f"[patch] complete: dmsh_build={'changed' if a else 'already patched'}, "
        f"profile_guess IoStore={'changed' if ue else 'already patched'}, "
        f"IPA builder={'changed' if b else 'already patched'}, "
        f"build_ipa.sh={'changed' if c else 'already patched'}")


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
