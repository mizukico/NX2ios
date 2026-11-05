# NX4Actions — Build Nintendo Switch Game Ports for iOS

**English** | [简体中文](README.zh-CN.md)

Build an unsigned iOS IPA with [NxNative](https://github.com/seedds/nxnative) through GitHub Actions on a cloud macOS runner. This project is an optimization of the workflow described in the [original Reddit guide](https://www.reddit.com/r/NativePortsOniOS/comments/1xh334e/how_to_compile_switch_games_into_native_ios_apps/), with a primary focus on reducing macOS runner disk usage. It provides the workflow and CI helper patches; it does not include game files, title keys, or upstream NxNative source code.

> **Status:** Community-maintained workflow. A successful build does not guarantee that a particular game will boot or run correctly on every iPhone or iOS version.

## Overview

The workflow is manually started from the **Actions** tab and offers two build paths:

| Device selection | Build source | Intended path |
| --- | --- | --- |
| iPhone 15 or older (BC fallback) | [mianmuhammadse/nxnative](https://github.com/mianmuhammadse/nxnative) at a pinned commit | BC-texture fallback |
| iPhone 15 Pro/Pro Max or newer (standard) | [seedds/nxnative](https://github.com/seedds/nxnative) at `main` | Standard texture path |

These labels select build configurations; they are not compatibility guarantees. Check the upstream project and your device's capabilities before choosing.

## What this repository adds

- **One-click workflow dispatch:** choose the device path and optionally provide a 16-character base-game title ID.
- **Private input links:** download the base game package, optional update/DLC, and `prod.keys` from Google Drive links stored as GitHub Actions secrets.
- **Package preparation:** accepts direct NSP/XCI/NSZ/XCZ packages and extracts supported RAR archives containing those packages.
- **Title ID selection:** uses the supplied override when present; otherwise attempts to detect the base title ID from the package.
- **Disk-conscious CI helpers:** applies local patches to the checked-out NxNative build scripts and monitors runner disk usage.
- **Standard-path RomFS handoff:** the Standard/NVN path pauses after shader splitting and before Metal compilation, uploads the standalone `RomFS.img` as the `NxNative-ROMFS` artifact, then resumes the cached build and releases the local RomFS image to save disk space.
- **Build artifacts:** uploads the resulting unsigned IPA and available build logs.

**BC fallback warning:** the BC fallback branch has not received the same disk-space optimizations and has not been specifically validated by this repository's testing. Its build may fail, and even a completed IPA is not a guarantee that the game will launch or run. No result is guaranteed for this branch.

## Requirements

- A GitHub account and a repository containing this workflow.
- Google Drive links that the runner can download without interactive sign-in.
- Your own legally obtained game package(s) and a matching `prod.keys` file.
- Awareness of GitHub Actions runner availability, execution limits, and artifact retention.

**Never commit game dumps, `prod.keys`, download URLs, access tokens, or other credentials to this repository.** Keep the repository private if its workflow configuration or logs contain information you do not want public.

## Setup

### 1. Add the required repository secrets

In your repository, open **Settings → Secrets and variables → Actions → New repository secret**.

Add these exact names:

| Secret | Required | Value |
| --- | --- | --- |
| `Game_URL` | Yes | Google Drive sharing URL for the base game package or supported RAR archive |
| `Keys_URL` | Yes | Google Drive sharing URL for `prod.keys` |
| `Update_URL` | No | Google Drive sharing URL for the update package/archive |
| `DLC_URL` | No | Google Drive sharing URL for the DLC package/archive |

The workflow downloads the files using `gdown`. Make sure each link is accessible to the runner and points to the intended file. Add update/DLC secrets only when you want to include those files.

### 2. Start a build

1. Open the repository's **Actions** tab.
2. Select **NxNative - Generic IPA Builder**.
3. Click **Run workflow**.
4. Select the device/build path.
5. Keep the profile ID at its default, or clear/override it only when you know the correct base-game title ID.
6. Click **Run workflow** to start.

### 3. Retrieve the outputs

When the run finishes, open its summary and download the artifacts:

- **`NxNative-IPA-Standard`** or **`NxNative-IPA-BC-Fallback`** — the unsigned IPA.
- **`NxNative-ROMFS`** — the standalone RomFS image uploaded by the Standard path when the NVN handoff is used.
- **`NxNative-Build-Logs`** — diagnostic logs and available game survey/build log folders.

GitHub downloads artifacts as ZIP files. Extract both files. **For the Standard/NVN `--romfs separate` build, you need BOTH the IPA and the matching `RomFS.img`; the IPA alone does not contain the game data and is not sufficient to play.**

After installing the IPA, place the image in the installed app's container at:

`<App Container>/Documents/romfs.img`

Use the exact filename `romfs.img` (lowercase). Do not put it inside `DmIOS.app`, `Payload`, or the app's `romfs` resource folder. The upstream project provides [`scripts/push_romfs.sh`](https://github.com/seedds/nxnative/blob/main/scripts/push_romfs.sh) to copy the image to the app's Documents directory; its [packing/deployment documentation](https://github.com/seedds/nxnative/blob/main/docs/development.md) describes the separate-RomFS deployment. Run the helper while the app is installed, using the device UDID, the app bundle ID, and the downloaded image. The image must match the game/version used to build the IPA; when the game version or extraction changes, transfer the matching image again.

The `NxNative-ROMFS` artifact is a separate game-data image, not an installable app.

## Disk-space optimizations

The main engineering goal of this repository is to reduce peak disk usage on the GitHub-hosted macOS runner, especially during the memory- and disk-intensive Metal shader compilation stage. The workflow applies these measures:

1. **Remove source download/staging files after extraction.** Once the game packages have been prepared in the build input directory, the workflow deletes the downloaded `.download` copies and temporary extracted RAR directories. The actual game packages required by NxNative are retained.
2. **Upload `RomFS.img` after shader splitting.** On the supported Standard/NVN separate-RomFS path, the builder pauses after shader splitting and before Metal compilation. The standalone RomFS image is uploaded as the `NxNative-ROMFS` artifact while it still exists on the runner.
3. **Delete the local `RomFS.img` before Metal compilation.** After the artifact upload, the workflow re-enters the cached build. The CI patch removes the local RomFS image before Metal compilation, maximizing the disk space available to Xcode/Metal.
4. **Build the IPA with `--romfs separate`.** Since the local image has been released, the IPA is packaged without embedding the game RomFS. The matching image is delivered separately and must be copied to the app container's `Documents/romfs.img`.

### Measured example: Final Fantasy Resonance (Asian edition)

The disk optimizations were developed primarily around **Final Fantasy Resonance (Asian edition)**. In a measured build of this title:

| Output / measurement | Observed value |
| --- | ---: |
| Final unsigned IPA | **6.58 GB** |
| Separate `RomFS.img` | **8.35 GB** |
| Lowest free disk space during the Metal compilation peak, after the original XCI and local `RomFS.img` had been removed | **430 MB** |

This is an observed result from that particular build, not a general capacity guarantee or a benchmark for every game. The combined IPA and RomFS image are much larger than the original XCI in this case. That may be a characteristic of this game's content, extraction, and build outputs; other games can have very different size and disk-usage profiles. The 430 MB remaining-space figure also shows that this workflow is still close to the runner's storage limit for this workload.

### CI helper: `.github/scripts/nxnative_ci_guard.py`

The added Python script is not a game patch and does not modify game content. It provides workflow-specific disk management and safe build-script integration:

- **Pre-clean:** removes only stale workflow-owned `GameFiles` / `nxnative` directories and old disk-monitor files from the runner temp directory; it deliberately leaves shared Homebrew, Xcode, and runner-wide caches alone.
- **Patch upstream build scripts:** adjusts the shader build cleanup behavior without deleting intermediate shader files before all shader-finalization tasks have finished, avoiding a cleanup race.
- **Manage the RomFS two-pass build:** patches the Standard upstream builder to stop after successful shader splitting, stage the image for artifact upload, and remove the local image on the second pass before Metal compilation.
- **Keep separate-RomFS IPA packaging valid:** patches `build_ipa.sh` to skip the RomFS marker check only when separate mode is selected and the image has intentionally been released. Normal validation remains in place when the image exists.
- **Disk monitoring and reporting:** records free disk space, filesystem usage, build progress, and sizes of relevant build directories at intervals; the final report helps identify which stage consumes the runner's storage.

The script is invoked by the workflow for pre-cleaning, patching, starting/stopping the monitor, and reporting. It is what coordinates the repository's disk-space safeguards; it does not itself perform the game extraction or Metal compilation.

## Build flow

```text
Checkout selected NxNative source
        |
Download game package(s) and prod.keys
        |
Prepare package files and detect title ID
        |
Apply CI guard patches and prepare shader toolchain
        |
Run NxNative builder
        |
        +-- BC fallback: normal build path
        |
        +-- Standard/NVN:
                extract / rewrite / split shaders
                pause before Metal compilation
                upload RomFS.img artifact
                rerun builder and reuse cached work
                release local RomFS image
                compile Metal shaders and package IPA
        |
Upload IPA and build logs
```

The Standard RomFS handoff is conditional: it only occurs when the selected Standard build reaches the supported NVN + separate-RomFS path and the builder creates the handoff marker and image. Other graphics paths may finish the IPA in the first pass and skip the RomFS artifact.

## Repository layout

- `.github/workflows/build.yml` — GitHub Actions workflow.
- `.github/scripts/nxnative_ci_guard.py` — CI helper that patches supported upstream build scripts, manages disk-safe cleanup, and runs the disk monitor.
- `README.md` — English documentation (default).
- `README.zh-CN.md` — Simplified Chinese documentation.

The workflow checks out NxNative at run time. This repository is not a fork or mirror of either upstream source repository.

## Workflow differences and reference YAML

This repository's workflow contains repository-specific CI integration, including the two upstream source selections, secret-based downloads, package preparation, title-ID detection, disk monitoring, CI guard patches, and the conditional Standard/NVN RomFS handoff described above.

**A verified line-by-line comparison with the Pastebin YAML at [https://pastebin.com/XbJt5p3c](https://pastebin.com/XbJt5p3c) is not included yet.** The Pastebin page and its raw/download endpoints could not be retrieved in the current editing session, so listing exact additions, removals, or changed values would be guesswork. If you provide the YAML text (or an accessible raw copy), this section can be replaced with an exact comparison table.

## Troubleshooting

- **Download step fails:** verify the secret name, Google Drive sharing permission, and that the URL identifies a downloadable file.
- **Title ID detection fails:** check that the base game package is complete and that the correct title ID is entered in the workflow input.
- **Shader/Metal build fails:** inspect the first meaningful error in the build log; later failures may be consequences of the first one.
- **RomFS artifact is absent:** the handoff is only expected for the Standard/NVN separate-RomFS route. Check whether the run actually reached shader splitting and whether the `ready` handoff marker was created.
- **IPA artifact is absent:** the job must reach the IPA upload step; inspect the first failed workflow step.
- **Game builds but does not run:** build success is not a compatibility guarantee. Verify the game version, update/DLC, keys, selected build path, and upstream compatibility notes.

When sharing logs for help, remove private URLs, tokens, repository details, and other credentials. Never share your keys file or game dump.

## Upstream projects

- [seedds/nxnative](https://github.com/seedds/nxnative) — Standard build source.
- [mianmuhammadse/nxnative](https://github.com/mianmuhammadse/nxnative) — pinned BC fallback source.
- [NxNative - Generic IPA Builder workflow](.github/workflows/build.yml) — this repository's workflow.
