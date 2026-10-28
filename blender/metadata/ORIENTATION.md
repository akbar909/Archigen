# Asset mounting convention

Model axes in `mounting` refer to the original GLB (glTF coordinates, Y up).
`front_axis` points away from the back plate, toward the artwork, mirror face,
clock dial, or light fixture. `up_axis` points toward its top.

The editor normalizes this front to +Z and then points it along the selected
wall's inward normal. Blender normalizes it to -Y (Z up). Frontend semantic
rotation is clockwise; Blender wall rotation must use the opposite sign.

Each reviewed record has `orientation_verified: true` and an
`orientation_version`. Width and depth alone must never decide which side is
the front: lamps project outward and artwork can have a different back texture.
When uploading a new wall asset, review cardinal views and add these fields
before marking it verified. Increment the version when correcting orientation.
Source GLBs do not need to be rewritten or reuploaded to S3.

`surface` is `wall`, `floor`, or `tabletop`. Standing mirrors and desk clocks
belong in the furniture catalog, not the wall-decoration picker.

Regenerate inventory with `node blender/scripts/audit_assets.mjs`, then run
`backend/.venv/Scripts/python.exe blender/scripts/audit_metadata.py`. The latter
reports all metadata/model mappings, dimensions, missing files and unverified
wall assets in `blender/metadata-audit.json`. To review model fronts visually,
run `audit_wall_orientations.py` using headless Blender.
