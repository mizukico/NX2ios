# NX2ios — Build Nintendo Switch Game Ports for iOS

**English** | [简体中文](README.zh-CN.md)

Build an unsigned iOS IPA with [NxNative](https://github.com/seedds/nxnative) through GitHub Actions, using a cloud macOS runner. This repository provides the workflow and CI helper patches; it does not include game files, title keys, or upstream NxNative source code.

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

The BC fallback uses its own pinned upstream revision and does not receive the Standard-only `--romfs separate` argument or the Standard RomFS handoff.

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

GitHub downloads artifacts as ZIP files. Extract the IPA from its ZIP before using your normal iOS sideloading method. The ROMFS artifact is a separate build output; it is not the IPA.

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
