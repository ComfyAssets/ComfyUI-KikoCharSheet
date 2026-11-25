# Pose pictures

These are the pose pictures the Pose Picker shows and sends to the image model.

- `img/grey/` and `thumbs/grey/`: the standard set, one render per pose, with a small thumbnail.
- `img/grey_wide/` and `thumbs/grey_wide/`: a wide-lens version. It holds only the renders that differ from the standard set; a pose without one uses the standard render.

Each file is named after the id of the pose it shows, as listed in the gallery project's pose data.

They are Blender renders of a 3D figure, made for this pack. The poses follow the pose drawings by ギア (@giaaibusi) in the [gallery project](https://github.com/anhao/ai-pose-gallery-zh), which were used as reference. None of those drawings is included here.

## Licence

The pictures in this folder are dedicated to the public domain under CC0 1.0 Universal. See `LICENSE` in this folder. You may use them for anything, with or without credit. This covers the pictures only, not the 3D model they were rendered from, which is not part of this repository.

To rebuild the sets from new renders, see "Pose pictures" in `docs/LICENSES-AND-SETUP.md`.
