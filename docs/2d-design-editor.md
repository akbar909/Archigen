# 2D design editor

Open **2D CAD Plan** to edit the active version. The editor uses the project's
existing JSON draft and Save/Save as Version flow. Unsaved edits also appear in
the JSON viewer. **Save changes** in the top bar is the single save entry point;
it offers overwrite or save as a new version. Save the draft, then choose
**Build 3D** in the editor when you want a new model. Saving never starts Blender,
including changes to an already approved layout. The generated design uses the entire workspace without the initial
chat panel or Design Wizard.

## Editing

- Select and drag rooms, walls, doors, windows, furniture, or stairs. Room and
  furniture selections expose eight resize handles. Furniture has a rotation
  handle and numeric rotation, mirror, duplicate, alignment and centering actions.
- Room origins are the south-west corner. Furniture positions are their centers.
  Geometry remains in metres, regardless of display units. Numeric fields accept
  explicit units such as `12 ft`, `3.65 m`, `100 mm`, and `6' 2"`.
- Draw a room with the Room tool. Draw a partition across a room with Partition,
  or use its inspector to split it at the midpoint. Shift-select two adjacent
  rooms to merge. Merges require a full shared edge forming a rectangle; this
  preserves the rectangular room contract used by the backend and Blender.
- Place doors/windows near a wall. Drag an opening along walls or around corners.
  Its host, room references, offset, jamb clearance and elevation are maintained.
  Inspector controls include swing/hinge, width presets, sill height, and equally
  spaced window arrays. Double and sliding doors have distinct CAD symbols.
- Choose an asset from Furniture, then tap a room to place it. Desktop users can
  drag from the palette. The synchronized catalog is preferred; the existing
  local catalog is the fallback. Marquee-select furniture from empty canvas,
  or Shift-click, to group, align, distribute or delete it.
- Add, duplicate, reorder and delete storeys from the floor bar. Select **Stair**,
  choose a shape, and use **Add upper floor** if no destination exists. This keeps
  the lower floor active. Click a clear area in a sufficiently large room; the
  footprint is centered and clamped inside that room. Move furniture first if it
  blocks the footprint on either floor. A short success message confirms placement.
  Straight, L and U flights synchronize the
  canonical `connects` and `stair_openings` records used by Blender. The ghost
  underlay displays the floor below without making it selectable.
- Properties with nothing selected exposes units, storey height/slab thickness,
  plot dimensions and setbacks. Garden, balcony, terrace and garage zones use
  the existing room types and site rendering. Existing exterior features retain
  their saved geometry.

## View and history

Drag with Pan (or Alt-drag) to move the viewport; use the wheel, pinch, zoom
buttons or Fit Plan to change the view. Measure records the distance between
two taps. Layers independently control visibility and selection locking.

`Ctrl/Cmd Z` undoes a transaction, `Ctrl/Cmd Shift Z` or `Ctrl Y` redoes,
`Ctrl/Cmd S` saves, `Ctrl/Cmd D` duplicates furniture, and Delete removes the
selection. Escape cancels an active gesture. `V` selects, `H` pans, and `G`
toggles snapping. Hold Shift while dragging to bypass snapping.

Drag previews do not modify the project JSON until release. Pointer cancellation
or loss of focus discards the preview. Up to 100 transactions are retained for
the current version in memory, including AI edits and canonical save repairs.
Changing versions/discarding a draft establishes a fresh baseline. History
reconciles 3D changes when returning to the 2D view.

Strict mode is the default and rejects newly introduced physical conflicts.
Warning mode is an explicit alternative that permits edits and highlights collisions.
The inspector can be expanded on phones, and expands when its AI input is focused.
The debounced diagnostic list covers
room overlap, project dimension standards, openings and spacing, furniture,
door swings, stair shafts, daylight and doorway connectivity. These checks use
the project's design standards; they do not certify compliance with a local
building code.

## Natural-language drafts

Select one room, furniture item, opening, wall or stair. **Edit with AI** appears
at the top of its inspector, with the selected element and floor shown as context.
Instructions such as “make room wider”, “make it deeper by 30 cm”, “rotate it
45 degrees” and “move it left” use that element's exact identifier, including
when several rooms share a type. The initial generation chat is hidden after
the design is created. Use the sidebar's **New Version** action or the Save
dialog to create another version. Local edits use the authenticated
`POST /api/projects/:project/versions/:version/layout/refine` endpoint.

Supported instructions reuse the existing room resize, style and furniture
refinement handlers and add opening movement, swing/hinge flips and sill height.
Compound instructions are transactional: an unsupported clause rejects the whole
request. Unsupported edits return a useful error rather than regenerating the
house. The endpoint checks version ownership, resolves selection IDs against the
supplied draft, and does not write to the database.

Approval conflicts appear as concise, selectable rows in **Design checks**.
The toast gives the count; raw wall and door identifiers are not appended to it.
**Repair door links** rehosts doors on a real shared wall when one exists.
Main entrances and garage doors connect their room to `exterior`, which is an
outside endpoint rather than a second room. They stay on exterior walls. Select
the entrance and ask **Edit with AI** to "fix this main gate" or "repair this door"
to repair its host and clearance while preserving its intended connections.
The separate **MAIN GATE** drawn at the plot boundary is a site feature; selecting
the house entrance edits the entrance door. A failed edit shows its reason in
both the inspector and a short toast.
If a room move disconnected the rooms completely, undo that move or put the door
on a suitable shared wall; the editor does not silently erase its intended link.

## 3D build status

Explicit approval, Build 3D and retry actions start a background job and
return HTTP 202 immediately. Version reads expose `generation_3d` with a job ID,
running/completed/failed status, UTC timestamps, and a short failure reason.
Repeated requests join an active build. Completion updates match the job ID so
an older attempt cannot replace a newer model.

The editor displays the running or failed status above its footer. A retry keeps
the previous preview until the new job completes; an old GLB URL does not count
as completion. Polling covers the default 600-second worker limit and 630-second
backend timeout instead of stopping after 200 seconds. If the backend restarts
and loses a background thread, the saved job eventually reports a timeout and
can be retried. Detailed Blender process errors remain in the worker/backend logs.

Deploy the backend and frontend together for this status protocol. Blender
geometry/asset changes separately require the script and metadata sync described
in [worker troubleshooting](blender-worker-troubleshooting.md).

Saving a draft updates its saved JSON without regenerating the model. A temporary
asset added and then deleted before saving cancels that addition, including its
empty helper collections and deletion marker. Existing saved asset deletions and
other edits continue to show **Save changes**.

## Verification

From `frontend`:

```powershell
node --test src/utils/*.test.mjs tests/*.test.mjs
node tests/run-cad-browser.mjs
npm.cmd run build
```

From the repository root:

```powershell
backend/.venv/Scripts/python.exe -B -m unittest discover -s backend/tests
backend/.venv/Scripts/python.exe -B backend/tests/run_cad_blender.py --blender 'C:/Program Files/Blender Foundation/Blender 5.1/blender.exe'
```

Browser checks use a local mock API and cover six viewport sizes from 320 px
phones through desktop, real pointer gestures, unit inputs, undo/redo,
wall-hosted openings, splitting, layers, floor actions, local AI draft history,
strict collisions, the asset palette, touch cancellation and pinch zoom.
The Blender contract test starts with frontend-generated JSON, edits rooms,
duplicates a floor, mirrors furniture and exports all three stair types,
checking schema, preflight, GLB metadata and furniture inventory.
