# Character Sheet Pickers for ComfyUI

Four ComfyUI nodes that pick references for a character sheet and prepare them for MiniMax H3 Image. They work with the H3 Character Sheet Designer pack, but do not need it.

| Node | What it does |
|---|---|
| Portrait Picker (Char Sheet) | Pick a portrait from the gallery, or one of your own uploads. Outputs the image and a prompt. |
| Costume Picker (Char Sheet) | Pick a costume and a view (front, diag, side, back). Outputs the image and a prompt. |
| Pose Picker (Char Sheet) | Pick up to 13 poses, in order. Flip any of them, and choose mannequin or depth images. |
| Pose Sheet Designer (Char Sheet) | Lays the poses out on one layout image and writes the prompt for it. |

All four are in the `CharSheet` category. Each picker shows a browsable panel inside the node, with search, filters, safe mode, your own uploads and a full-screen view. The panel follows the ComfyUI language (English or Chinese).

## Three ways to use poses

1. **Pose sheet.** Pose Picker, then Pose Sheet Designer, then H3 Image Conditioning. The designer outputs `prompt`, `width`, `height` and `image_1` to `image_3` (character, layout, outfit). Workflow: `workflows/charsheet-minimax-h3-pose-sheet.json`.
2. **H3 references.** Send the portrait to the H3 Character Sheet Designer as `character_image`, the costume as `reference_image_1`, and `pose_1` and `pose_2` as `reference_image_2` and `_3`. Workflow: `workflows/charsheet-h3-references.json`.
3. **One image per pose.** The Pose Picker outputs lists (`poses`, `pose_prompts_en`). ComfyUI runs what follows once per pose. Workflow: `workflows/charsheet-one-per-pose.json`.

The example workflows use the author's local model, text encoder and VAE file names (taken from the H3 Character Sheet example workflow). Change them to the names of your own files. They need the nodes of this pack and ComfyUI's MiniMax H3 nodes. The H3 references workflow also needs the H3 Character Sheet Designer pack.

## Blank image slots and prompt text

The designer always outputs three images, filled in the order character, layout, outfit. A picture you do not connect is left out and the later ones move up. Unused `image_n` outputs are blank 64x64 white images. The `picture_count` output says how many are real. Connect only the first `picture_count` images to the conditioning node. For example, disconnect `image_3` when no costume is used.

`character_prompt` does not need a character image. It adds a sentence that describes the person, and it works with or without a portrait. `outfit_prompt` only has an effect when an outfit image is connected. Without an outfit image, the outfit sentences are left out, including the text of `outfit_prompt`. The prompt tells the model to copy garments, colours and materials from the outfit picture; the `outfit_prompt` text only lists the garments.

The Costume Picker has an `include_footwear` switch, on by default. It adds an instruction to the costume's prompt text: wear the shoes shown in the outfit picture, or, when off, leave the shoes out. It takes effect where that text is used, so connect the picker's `prompt_en` to `outfit_prompt` (the example workflows do).

`style` is one sentence added near the end of the prompt. The default asks for a photorealistic studio photograph. Replace it for another look (for example an illustration style), or clear it to leave the style to the model.

## Portrait uploads

A portrait upload that is not already 4:5 shows a crop frame over the preview. Drag the frame to choose the area; only that area is stored, as a PNG. Costume and pose uploads are stored as they are.

## Install

1. Put this folder in `ComfyUI/custom_nodes/` (a clone or a symlink).
2. Copy the gallery images and data into `assets/`. You need a clone of the ai-pose-gallery fork with its images downloaded (see its README, `scripts/download.py`):

   ```
   python3 scripts/setup_assets.py --from /path/to/ai-pose-gallery-en
   ```

   This copies about 1.2 GB. Use `--force` to replace an existing `assets/`. Without `assets/`, the nodes raise an error that names this script.
3. Restart ComfyUI.

Python needs nothing beyond what ComfyUI ships. Run the Python tests with ComfyUI's Python environment, because plain `python` has no torch or Pillow: `<ComfyUI>/venv/bin/python -m unittest discover -s tests -p 'test_*.py'`. Run the JS tests with `npm test`.

Licences, image sources and what you may do with the images: [docs/LICENSES-AND-SETUP.md](docs/LICENSES-AND-SETUP.md).

## Screenshots to add

- Portrait Picker panel
- Costume Picker panel with the view menu
- Pose Picker panel with the tray
- Full-screen view
- Pose Sheet Designer with the layout preview
- The pose-sheet workflow

## Credits

- Gallery data and the picker idea: [anhao/ai-pose-gallery-zh](https://github.com/anhao/ai-pose-gallery-zh).
- Panel look and the node-UI pattern: [H3 Character Sheet Designer](https://github.com/ukr8b3g-cmyk/H3-Character-Sheet-Designer) by ukr8b3g-cmyk.
- Code: MIT, see [LICENSE](LICENSE). The licence does not cover any image.
