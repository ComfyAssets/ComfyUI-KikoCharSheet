# Licences, image sources and setup

## What you get and what you download

- **This pack** gives you the nodes, the English names for everything in the galleries (`locales/en/data.json`) and the pose pictures (`poses/`). All three are in this repository.
- **The gallery's images and data are not in this repository.** The setup script downloads your own copy from the gallery project into `assets/`, which is git-ignored.

Why it works this way: the realistic-costume images have no stated licence, so nobody but their author may redistribute them, and the CharaDB licence forbids redistribution outright. Shipping the images with this pack would mean redistributing other people's work without permission. Downloading your own copy from the source keeps that decision, and the responsibility for how the images are used, with you.

## What is licensed how

- The code in this repository is MIT. Owner: Vito Sansevero. See `LICENSE`.
- The English names in `locales/en/data.json` are this project's translations, also MIT. The Chinese names they translate come from the gallery project's data.
- The pose pictures in `poses/` are this project's own renders. They are dedicated to the public domain under CC0 1.0 Universal, see `poses/LICENSE`: use them for anything, no credit needed.
- Parts of the code are adapted from the gallery project's ComfyUI nodes ([anhao/ai-pose-gallery-zh](https://github.com/anhao/ai-pose-gallery-zh), MIT, Copyright (c) 2026 Anhao): costume view selection, the safe-mode category lists and the Chinese prompt wording.
- The gallery images are third-party reference material, under the terms in the table below. They are not under this repository's licence.

## Where the images come from

This information comes from the README of the gallery project ([anhao/ai-pose-gallery-zh](https://github.com/anhao/ai-pose-gallery-zh)), its `docs/GIA-ANIME-COSTUMES.md` and its `docs/SHISEI-COSTUMES.md`. It was read on 2026-11-23. Check the originals before you rely on it.

| Library | Source | What is known |
|---|---|---|
| Poses | Pose names, categories and ids: the gallery project's data. Pose pictures: grey 3D model renders made for this pack. | The gallery's own pose pictures (ギア's mannequin drawings and depth images, no licence stated) are not used and the setup script does not copy them. The renders ship with this pack in `poses/`, under CC0 1.0. |
| Realistic costumes | ギア (@giaaibusi), ai-costume-gallery.pages.dev | Same: copyright with the author, no licence stated. |
| Portraits | ギア (@giaaibusi), ai-portrait-gallery.pages.dev | The gallery project states CC0 1.0 for the portrait gallery. |
| Chinese historical costumes (Shisei) | Shisei / wquguru, github.com/wquguru/shisei | CC0 1.0 for the images and their data, per the gallery project's `docs/SHISEI-COSTUMES.md`. 57 outfits, 227 views. These are AI-generated references, not historical reconstructions. |
| Anime costumes (CharaDB) | たき AI (@taki_auto), CharaDB | The CharaDB licence says: tags are CC0; images are for reference only; no redistribution; no use for real people or minors. The gallery project does not store these images. They load from the CharaDB site. |
| Anime costumes (ギア anime) | ギア (@giaaibusi), ai-costume-anime-gallery.pages.dev ("衣装集 アニメ版") | The gallery project keeps only a metadata snapshot. Images load from the origin site. It says to follow the author's own terms and that a code licence is not an image licence. |

What is not known: the exact licence of the realistic-costume images, and whether the original author allows any reuse beyond viewing. Its README describes the project as a translated archive for study and says the images must not be repackaged or sold. Contact the original authors if you need more than that.

## Hotlinked images

The CharaDB and anime costume images (about 1,760 entries) are not copied by the setup script. The costume picker loads them from the origin sites, so they need an internet connection. Both sets are hidden by default; the Costume Picker's **🌐 Anime sets** button shows them after you confirm their terms. See the README's *The anime costume sets*. Do not download, mirror or redistribute them, and do not commit them. If an origin site goes offline, those thumbnails and images stop working.

Only addresses listed exactly in the catalogue are fetched, with size and time limits. The picker does not fetch arbitrary URLs.

## Setup

One command downloads what the nodes need from the gallery project on GitHub and puts it into `assets/`. Run it in the pack's folder:

```
python3 scripts/setup_assets.py --download [--force]
```

On Windows: `python scripts\setup_assets.py --download [--force]`.

- It fetches the gallery data, the costumes and the portraits, about 470 MB, and nothing else. The gallery's pose pictures are not downloaded.
- It needs git. The files come straight from [anhao/ai-pose-gallery-zh](https://github.com/anhao/ai-pose-gallery-zh) to your machine; this pack does not host or pass on any of them.
- It fetches the gallery version this pack was last checked against. `--ref HEAD` takes the newest one instead.
- Existing assets are not overwritten unless you pass `--force`.

If you already have a clone of the gallery project, copy from it instead:

```
python3 scripts/setup_assets.py --from /path/to/ai-pose-gallery-zh [--force]
```

- The clone must contain `data/`, `img/` and `thumbs/`. If it does not, the script stops and says which are missing.
- The original-size files that the gallery project's own `scripts/download.py` fetches (about 6 GB) are left out, and so are its pose pictures. The script says how many.

### Pose pictures

The Pose Picker does not use the gallery's pose pictures, and the setup script does not download them. It shows each pose as a grey 3D model render made for this pack. The renders ship with the pack in `poses/`, so there is nothing to set up, and the picker lists only the poses that have one.

- They are Blender renders of a 3D figure, posed with the gallery's pose drawings as reference. The gallery's drawings themselves are not included.
- The build of the figure in the pose picture carries over into the generated person, which is why the renders use a slim model.
- There are two sets. `grey` is the standard one. `grey_wide` is a wide-lens version and holds only the renders that differ; a pose without a wide render uses the grey one. The Pose Picker's lens button switches between them.
- Workflows saved while the mannequin and depth pictures were still offered load with the grey set.

To rebuild the sets from new renders (PNG files named after the pose ids, for example `full_single_P018_front.png`), use the Python that runs your ComfyUI, because the script needs Pillow:

```
<ComfyUI>/venv/bin/python scripts/add_pose_set.py --style grey --from /path/to/renders
<ComfyUI>/venv/bin/python scripts/add_pose_set.py --style grey_wide --from /path/to/wide-renders
```

It writes each render to `poses/img/<style>/` as WebP, with a small thumbnail in `poses/thumbs/<style>/`, and replaces files that are already there.

Your own uploads are separate. They go into the ComfyUI input folder under `charsheet/<portrait|costume|pose>/`, never into `assets/`. Only PNG, JPEG and WebP files are accepted.

## Credits

- Gallery data, translations and tooling: [anhao/ai-pose-gallery-zh](https://github.com/anhao/ai-pose-gallery-zh).
- Original galleries: ギア (@giaaibusi). Anime costumes: たき AI (@taki_auto), [CharaDB](https://charadb-2fi.pages.dev/).
- Interface inspiration: [H3 Character Sheet Designer](https://github.com/ukr8b3g-cmyk/H3-Character-Sheet-Designer) by ukr8b3g-cmyk.

## Safe mode and content

The galleries include adult poses and costumes. Safe mode is on by default and hides them. People under 18 must not turn it off.
