# Stair generation and the 25 x 40 ft two-storey report

The reported plan combined several independent failures. Floor-heading room
lists lost their assignments and counts; plot dimensions and entrance direction
in prose were not authoritative. The layout engine then searched for a stair
after packing occupied rooms, permitting an upstairs bedroom to contain its
opening. The CAD view drew every configuration as a ten-line straight stair.
Backend preflight checked stated width/headroom and alignment but did not
calculate the tread depth. JSON schema validation also ignored critical
geometric errors recorded by preflight.

Generation now reserves a stair lobby on each storey before room placement.
The stair and its opening share coordinates. Rooms, doors, furniture and slab
openings use the same reserved geometry. Preflight rejects short runs, narrow
flights, insufficient landings, excessive riser height, private-room shafts,
door swings, blocked doorway approaches and obstructed stair approaches.
Critical preflight errors also prevent successful generation responses.

`backend/utils/stair_geometry.py` and `frontend/src/utils/stairGeometry.js`
calculate the geometry used by the Blender and CAD builders. Their project
targets are 0.25 m minimum going, 0.90 m minimum clear flight width, a turn
landing at least as deep as the declared clear flight width, and 0.19 m maximum
riser height. These targets are application rules, not local building-code
certification. Generation uses 1.00 m clear width, exceeding the requested
3 ft (0.9144 m).

For the current 3.00 m storey height, generation uses 18 risers of approximately
0.1667 m. Its U stair is 2.20 x 3.35 m with a 1.00 m turn landing. Under the
builder's nine-module-per-flight convention, the going is
`(3.35 - 1.00) / 9 = 0.2611 m`. The clear approach outside the footprint must be
reserved separately. Changing storey height recalculates the required count
and footprint; claiming a larger `tread` field cannot override the measured run.

The original 25 x 40 ft plot is retained as 7.62 x 12.19 m. Its default setbacks
leave a 6.10 x 8.54 m envelope. The shelf packer previously needed 16.40 m depth
because it arranged large room bands and a separate circulation strip in
sequence. That number described its packing strategy, not an architectural
minimum for the house.

A compact planning alternative now handles this north-facing two-storey room
program in that envelope. The U stair runs across the plot, occupies
3.25 x 2.20 m, and retains the 1.00 m clear width, 1.00 m turn landing and
0.25 m going. Its east approach is 1.15 m deep. Both bathrooms occupy the same
1.50 x 2.60 m rectangle. Upstairs bedrooms open to the family lounge, which also
serves the front/north balcony; neither bedrooms nor the balcony become a
passage to other rooms. No extra corridor is inserted.

This strategy applies only to explicitly compact requests matching that room
program, a north frontage, and a buildable width of 6.10–6.80 m and depth of
8.50–11.00 m. Other programs retain the general packer. It does not change
requested setbacks, plot dimensions or room inventory. Compact room targets
are explicit in `compact_home_layout.py` and mirrored in the client validator;
stairs retain the same physical targets. The guest room uses a single bed,
the upstairs rooms use double beds, and optional bedside tables are omitted.
Exterior windows are positioned away from the available headboard walls.

Across-plot stairs use `run_axis: "x"` with world-space width/depth. Backend
checks, CAD symbols, slab openings, editor synchronization and Blender all use
the same orientation. The Blender worker needs the updated
`generate_house_vertical.py`; backend/frontend updates are deployed separately.

Saved plans are not automatically rearranged. Regenerate a plan after updating
the backend, frontend and Blender worker. Existing invalid plans can be edited,
but must pass the geometric checks before building 3D.

Regression coverage is in `backend/tests/test_prompt_floor_program.py`,
`backend/tests/test_stair_geometry.py` and
`frontend/src/utils/stairGeometry.test.mjs`, together with the existing pipeline,
editor and exterior tests. A headless `multi_floor_stairs` Blender integration
also exercises actual stair construction, slab openings and GLB export.
