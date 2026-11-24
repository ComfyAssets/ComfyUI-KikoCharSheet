# Licences, image sources and setup

## What you get and what you download

- **This pack** gives you the nodes and the English names for everything in the galleries (`locales/en/data.json`). Both are in this repository.
- **The images and gallery data are not in this repository.** You download your own copy from the gallery project and the setup script copies it into `assets/`, which is git-ignored.

Why it works this way: the pose and realistic-costume images have no stated licence, so nobody but their author may redistribute them, and the CharaDB licence forbids redistribution outright. Shipping the images with this pack would mean redistributing other people's work without permission. Downloading your own copy from the source keeps that decision, and the responsibility for how the images are used, with you.

## What is licensed how

- The code in this repository is MIT. Owner: Vito Sansevero. See `LICENSE`.
- The English names in `locales/en/data.json` are this project's translations, also MIT. The Chinese names they translate come from the gallery project's data.
- Parts of the code are adapted from the gallery project's ComfyUI nodes ([anhao/ai-pose-gallery-zh](https://github.com/anhao/ai-pose-gallery-zh), MIT, Copyright (c) 2026 Anhao): costume view selection, the safe-mode category lists and the Chinese prompt wording.
- The gallery images are third-party reference material, under the terms in the table below. They are not under this repository's licence.

## Where the images come from

This information comes from the README of the gallery project ([anhao/ai-pose-gallery-zh](https://github.com/anhao/ai-pose-gallery-zh)), its `docs/GIA-ANIME-COSTUMES.md` and its `docs/SHISEI-COSTUMES.md`. It was read on 2026-11-23. Check the originals before you rely on it.

| Library | Source | What is known |
|---|---|---|
| Poses (mannequin and depth) | ギア (@giaaibusi), gallery sites ai-pose-gallery.pages.dev and ai-pose-depth-gallery.pages.dev | The gallery project says the copyright belongs to the original author. It does not state a licence for the pose images. |
| Realistic costumes | ギア (@giaaibusi), ai-costume-gallery.pages.dev | Same: copyright with the author, no licence stated. |
| Portraits | ギア (@giaaibusi), ai-portrait-gallery.pages.dev | The gallery project states CC0 1.0 for the portrait gallery. |
| Chinese historical costumes (Shisei) | Shisei / wquguru, github.com/wquguru/shisei | CC0 1.0 for the images and their data, per the gallery project's `docs/SHISEI-COSTUMES.md`. 57 outfits, 227 views. These are AI-generated references, not historical reconstructions. |
| Anime costumes (CharaDB) | たき AI (@taki_auto), CharaDB | The CharaDB licence says: tags are CC0; images are for reference only; no redistribution; no use for real people or minors. The gallery project does not store these images. They load from the CharaDB site. |
| Anime costumes (ギア anime) | ギア (@giaaibusi), ai-costume-anime-gallery.pages.dev ("衣装集 アニメ版") | The gallery project keeps only a metadata snapshot. Images load from the origin site. It says to follow the author's own terms and that a code licence is not an image licence. |

What is not known: the exact licence of the pose and realistic-costume images, and whether the original author allows any reuse beyond viewing. Its README describes the project as a translated archive for study and says the images must not be repackaged or sold. Contact the original authors if you need more than that.

## Hotlinked images

The CharaDB and anime costume images (about 1,760 entries) are not copied by the setup script. The costume picker loads them from the origin sites, so they need an internet connection. Do not download, mirror or redistribute them, and do not commit them. If an origin site goes offline, those thumbnails and images stop working.

Only addresses listed exactly in the catalogue are fetched, with size and time limits. The picker does not fetch arbitrary URLs.

## Setup

First get your own copy of the gallery project (about 1.2 GB):

```
git clone --depth 1 https://github.com/anhao/ai-pose-gallery-zh.git
```

Then copy its images and data into this pack.

Linux and macOS:

```
python3 scripts/setup_assets.py --from /path/to/ai-pose-gallery-zh [--force]
```

Windows (from the pack's folder; use the Python that runs your ComfyUI, for example `python_embeded\python.exe` of the portable build):

```
python scripts\setup_assets.py --from C:\path\to\ai-pose-gallery-zh [--force]
```

- The source must contain `data/`, `img/` and `thumbs/`. If it does not, the script stops and says which are missing. A clone of the gallery project has all three, with the images the nodes use (about 1.2 GB). You do not need to run its `scripts/download.py`.
- That download script fetches the original-size files (about 6 GB more) that the gallery project keeps out of git. If you have run it, the setup script leaves those files out and says how many.
- The script always copies. There is no symlink option. The copy is about 1.2 GB.
- Existing assets are not overwritten unless you pass `--force`.

Your own uploads are separate. They go into the ComfyUI input folder under `charsheet/<portrait|costume|pose>/`, never into `assets/`. Only PNG, JPEG and WebP files are accepted.

## Credits

- Gallery data, translations and tooling: [anhao/ai-pose-gallery-zh](https://github.com/anhao/ai-pose-gallery-zh).
- Original galleries: ギア (@giaaibusi). Anime costumes: たき AI (@taki_auto), [CharaDB](https://charadb-2fi.pages.dev/).
- Interface inspiration: [H3 Character Sheet Designer](https://github.com/ukr8b3g-cmyk/H3-Character-Sheet-Designer) by ukr8b3g-cmyk.

## Safe mode and content

The galleries include adult poses and costumes. Safe mode is on by default and hides them. People under 18 must not turn it off.
