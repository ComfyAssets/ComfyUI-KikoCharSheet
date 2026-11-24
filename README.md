# Character Sheet Pickers for ComfyUI

Four ComfyUI nodes that pick references for a character sheet and prepare them for MiniMax H3 Image. They work with the H3 Character Sheet Designer pack, but do not need it.

| Node | What it does |
|---|---|
| Portrait Picker (Char Sheet) | Pick a portrait from the gallery, or one of your own uploads. Outputs the image and a prompt. |
| Costume Picker (Char Sheet) | Pick a costume and a view (front, diag, side, back). Outputs the image and a prompt. |
| Pose Picker (Char Sheet) | Pick up to 13 poses, in order. Flip any of them, and choose mannequin or depth images. |
| Pose Sheet Designer (Char Sheet) | Lays the poses out on one layout image and writes the prompt for it. |

All four are in the `CharSheet` category. Each picker shows a browsable panel inside the node, with search, filters, safe mode, your own uploads and a full-screen view. The panel follows the ComfyUI language (English or Chinese).

## What this pack changes and adds

The galleries and the idea of picking a portrait, a costume and a pose come from the projects credited below. This pack is a new set of nodes built around them. What is different here:

- **English throughout.** Every pose name, costume name, category, tag and hairstyle has an English translation (2,341 names, in `locales/en/data.json`). The pickers show them when ComfyUI is set to English, and the prompt outputs come in English and Chinese. The gallery project itself is in Chinese.
- **Your own images.** Each picker has an upload tile. Your pictures are stored in ComfyUI's own `input/charsheet/` folder, never inside this pack, and appear in the picker next to the gallery items. Portrait uploads get a 4:5 crop frame you can drag.
- **Pickers inside the node.** The gallery opens as a panel in the node itself, with search, filters, safe mode and a full-screen view. This follows the in-node panel of the H3 Character Sheet Designer; the gallery project's own ComfyUI nodes use a pop-up window.
- **Several poses at once.** The Pose Picker takes up to 13 poses in an order you choose, with a flip switch per pose and a choice of mannequin or depth images.
- **A pose sheet for MiniMax H3.** The Pose Sheet Designer lays the chosen poses out on one image and writes the prompt for it, so one generation gives the same character in every pose. It is modelled on the H3 Character Sheet Designer, which does this for fixed views (front, side, back) but not for free poses.
- **Prompt controls.** A style sentence you can edit, a switch for including the footwear, and wording that tells the model to copy the outfit from the picture.

### Nodes this pack is modelled on

- **The gallery project's ComfyUI nodes** ([anhao/ai-pose-gallery-zh](https://github.com/anhao/ai-pose-gallery-zh)): its Pose, Costume and Portrait pickers are the starting point for the three pickers here.
- **H3 Character Sheet Designer** ([ukr8b3g-cmyk](https://github.com/ukr8b3g-cmyk/H3-Character-Sheet-Designer)): the in-node panel, keeping the panel's state in one hidden field, and the idea of a designer node that outputs a layout image, a prompt and a size for MiniMax H3.

Some logic is adapted from the gallery project's nodes, which are MIT licensed: how a costume's views are chosen, which categories safe mode hides, and the Chinese prompt wording. The H3 Character Sheet Designer's approach was followed, not its code. No images from either are included.

## Three ways to use poses

1. **Pose sheet.** Pose Picker, then Pose Sheet Designer, then H3 Image Conditioning. The designer outputs `prompt`, `width`, `height` and `image_1` to `image_3` (character, layout, outfit). Workflow: `workflows/charsheet-minimax-h3-pose-sheet.json`.
2. **H3 references.** Send the portrait to the H3 Character Sheet Designer as `character_image`, the costume as `reference_image_1`, and `pose_1` and `pose_2` as `reference_image_2` and `_3`. Workflow: `workflows/charsheet-h3-references.json`.
3. **One image per pose.** The Pose Picker outputs lists (`poses`, `pose_prompts_en`). ComfyUI runs what follows once per pose. Workflow: `workflows/charsheet-one-per-pose.json`.

The example workflows use the author's local model, text encoder and VAE file names (taken from the H3 Character Sheet example workflow). Change them to the names of your own files. They need the nodes of this pack and ComfyUI's MiniMax H3 nodes. The H3 references workflow also needs the H3 Character Sheet Designer pack.

## Blank image slots and prompt text

The designer always outputs three images, filled in the order character, layout, outfit. A picture you do not connect is left out and the later ones move up. Unused `image_n` outputs are blank 64x64 white images. The `picture_count` output says how many are real. Connect only the first `picture_count` images to the conditioning node. For example, disconnect `image_3` when no costume is used.

`character_prompt` does not need a character image. It adds a sentence that describes the person, and it works with or without a portrait. `outfit_prompt` only has an effect when an outfit image is connected. Without an outfit image, the outfit sentences are left out, including the text of `outfit_prompt`. The prompt tells the model to copy garments, colours and materials from the outfit picture; the `outfit_prompt` text only lists the garments.

The Costume Picker has an `include_footwear` switch, on by default. It adds an instruction to the costume's prompt text: wear the shoes shown in the outfit picture, or, when off, leave the shoes out. It takes effect where that text is used: connect the picker's `prompt_en` to the Pose Sheet Designer's `outfit_prompt`. The `footwear_en` and `footwear_zh` outputs hold the footwear instruction alone, for prompts you write yourself; the one-per-pose workflow uses `footwear_en`.

`style` is one sentence added near the end of the prompt. The default asks for a photorealistic studio photograph. Replace it for another look (for example an illustration style), or clear it to leave the style to the model.

## Portrait uploads

A portrait upload that is not already 4:5 shows a crop frame over the preview. Drag the frame to choose the area; only that area is stored, as a PNG. Costume and pose uploads are stored as they are.

## Thanks and credits

Thank you to ギア (@giaaibusi) for the original pose, costume and portrait galleries, and to [Anhao](https://github.com/anhao/ai-pose-gallery-zh) for the Chinese gallery project that organised and translated them. Thanks also to たき AI (@taki_auto) for [CharaDB](https://github.com/taki-ttt/charadb), to the [Shisei](https://github.com/wquguru/shisei) authors for the Chinese historical costumes, and to ukr8b3g-cmyk, whose [H3 Character Sheet Designer](https://github.com/ukr8b3g-cmyk/H3-Character-Sheet-Designer) inspired the in-node panels. This pack exists because of their work. Please visit the original projects and give their creators the credit and support they deserve.

The aim here is to make these references convenient to use inside ComfyUI with MiniMax H3: pick a face, an outfit and poses in the node, with English descriptions and prompt text you can edit.

This is an independent adaptation. It is not endorsed by or affiliated with any of the creators above. It contains none of their images: you download your own copy from the gallery project, because the images are not ours to redistribute. If a creator or rights holder would like this pack, or any reference to their material, removed, I will gladly take it down.

Full credits, image terms and the reasons for the separate download: `docs/LICENSES-AND-SETUP.md`.

## Install

1. Put this folder in `ComfyUI/custom_nodes/` (a clone or a symlink).
2. Get your own copy of the gallery images and data. They are not part of this pack (see the credits above). Clone the gallery project; the images come with the clone, about 1.2 GB:

   ```
   git clone --depth 1 https://github.com/anhao/ai-pose-gallery-zh.git
   ```

3. Copy them into this pack's `assets/` folder:

   ```
   python3 scripts/setup_assets.py --from /path/to/ai-pose-gallery-zh
   ```

   On Windows, run it with the Python that runs your ComfyUI: `python scripts\setup_assets.py --from C:\path\to\ai-pose-gallery-zh`.

   This copies about 1.2 GB. Use `--force` to replace an existing `assets/`. Without `assets/`, the nodes raise an error that names this script.
4. Restart ComfyUI. The English names for poses, costumes and hairstyles ship with this pack, so there is nothing more to set up.

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
