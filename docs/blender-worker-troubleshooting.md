# Blender worker failures on EC2

The reported November 1 failure exited with code 1 during scene validation:
three furniture meshes overlapped door approaches in the kitchen and second
bedroom. The same run could not import external glTF buffers `Sofa_01.bin` and
`large_castle_door.bin`. It did not reach the 600-second worker timeout.

The placement pipeline now reconciles actual imported mesh bounds before scene
validation. Generated items can move to a safe position; intentional user
placements are preserved and rejected with a useful error when unsafe. Cached
glTF files validate their buffers/textures, download missing dependencies, or use
only the matching complete source GLB. The reported sofa and arched window have
matching source GLBs in the local asset library.

## Interior asset placement corrections

- Interior wall/window face normals are oriented toward the selected room before
  mounting Curtains 04 or another wall decoration. Existing reversed saved
  normals are corrected for display and export; exterior boundary faces retain
  their selected side.
- Browser replacements retain each instance's saved dimensions and room bounds.
  They no longer substitute the catalog's default bed size for a compact bed.
- `wardrobe_modern_01` now has wardrobe dimensions and its reviewed front axis.
  CAD, browser, and Blender use one canonical rotation; explicit saved rotations
  are not replaced by a second wall-facing guess during generation.
- The uploaded shower sets/heads have reviewed wall mounting defaults. Selecting
  a shower exposes **Up 0.1m** and **Down 0.1m**. Height is measured from its room's
  floor and constrained below the ceiling; saves retain the chosen height.
  Choose **Mount on wall → Right wall** in the preview or shower inspector, or
  select the bathroom's right wall and choose a shower in **Shower fixtures**.
  Changing walls discards the previous wall anchor so it cannot snap back.
- The imported interior door labels its solid panel `door_frame` and its fixed
  trim `door_casing`. The panel now hinges together with its handles rather than
  leaving the panel shut and rotating only its hardware.
- `arched_window_01.glb` is a real local asset. Window selection now prefers a
  stable standard model for ordinary windows and uses the arch when requested,
  rather than depending on filesystem traversal order.

These updates include Blender **metadata** as well as Python scripts. Use the
full incremental asset sync below, restart the worker and local backend, refresh
the frontend, save the draft, and regenerate the existing 3D model to replace
door/window geometry that is already baked into its GLB.

Saving 2D or 3D edits does not start a build. Use **Build 3D** or **Finalize Blender
GLB** explicitly after saving. Adding and then deleting an unsaved asset cancels
the addition and clears **Save changes** when no other draft differences remain.

Focused verification: from `frontend`, run
`node tests/run-editor-browser.mjs --interior-only` to load the real curtain,
bed and shower models, check room bounds, and test the height buttons on desktop
and mobile. `backend/tests/test_interior_assets.py` also checks the real Blender
door panel/handle hierarchy and mounted shower bounds when Blender is available.

## Check the current worker

Run these in the EC2 terminal; the observed container name is `archigen-worker`.
These commands do not print AWS keys or the container's full environment.

```bash
docker exec archigen-worker python3 -c "import worker_server as w; print('Worker timeout (seconds):', getattr(w, 'BLENDER_GENERATION_TIMEOUT_SECONDS', 'not exposed'))"
curl -sS http://127.0.0.1:5001/health | python3 -m json.tool
docker logs --since 30m --tail 300 archigen-worker 2>&1
docker stats --no-stream archigen-worker
free -h
docker inspect archigen-worker --format 'MemoryBytes={{.HostConfig.Memory}} OOMKilled={{.State.OOMKilled}} Restarts={{.RestartCount}}'
sudo journalctl -k --since '30 minutes ago' --no-pager | grep -Ei 'oom|out of memory|killed process|segfault'
```

`MemoryBytes=0` means no explicit container limit; host memory still limits the
process. The observed 913 MB limit alone does not prove OOM. HTTP 504 indicates
the worker generation timeout; HTTP 500 means a failed process or launch. The
updated health response exposes `generation_timeout_seconds` and
`restart_required`. New attempts preserve complete output in
`/app/blender/output/<house_id>_<suffix>.log`; the HTTP response names `log_file`.

```bash
docker exec archigen-worker sh -lc 'ls -lt /app/blender/output/*.log | head -n 5'
# Replace LOG_NAME with the filename from the worker response or listing.
docker exec archigen-worker tail -n 100 /app/blender/output/LOG_NAME
```

## Apply the script fixes

From the local project root in PowerShell:

```powershell
& '.\backend\.venv\Scripts\python.exe' '.\blender\scripts\upload_s3_scripts.py'
```

Then from the EC2 terminal, download the changed scripts and any missing asset
content. A second sync supports workers whose previous sync script did not yet
download the root worker server. Running the sync directly avoids the asset-sync
HTTP endpoint's separate 300-second request limit. Each command must finish
successfully before restarting.

```bash
docker exec archigen-worker python3 /app/blender/scripts/sync_s3_assets.py --direction download &&
docker exec archigen-worker python3 /app/blender/scripts/sync_s3_assets.py --direction download &&
docker restart archigen-worker
curl -sS http://127.0.0.1:5001/health | python3 -m json.tool
```

If the remote library lacks the matching GLBs, buffers, or metadata, upload the
complete local library first. Script-only uploads do not include those files.

```powershell
& '.\backend\.venv\Scripts\python.exe' '.\blender\scripts\sync_s3_assets.py' --direction upload
```

Restart the local backend and refresh the frontend for preflight/inspector
changes, then save the current draft and retry **Build 3D**. Door approaches that
are blocked by an intentional user placement must be cleared in the editor.

## Blender's separate Python dependencies

The Docker image now installs `boto3` into Blender's embedded Python as well as
the web worker's system Python. It also enables unbuffered worker output. A
script sync cannot change an image's installed packages. Rebuild the image using
the updated Dockerfile for a permanent fix. Check an existing container with:

```bash
docker exec archigen-worker blender --background --factory-startup --python-expr "import importlib.util; print('BLENDER_BOTO3_AVAILABLE:', importlib.util.find_spec('boto3') is not None)"
```

If it reports `False`, the currently pinned Blender 3.6 image can be repaired
in place with the following commands. This installation survives a container
restart but must be repeated if that container is replaced from the old image.

```bash
docker exec archigen-worker /opt/blender/3.6/python/bin/python3.10 -m ensurepip
docker exec archigen-worker /opt/blender/3.6/python/bin/python3.10 -m pip install --no-cache-dir boto3
```
