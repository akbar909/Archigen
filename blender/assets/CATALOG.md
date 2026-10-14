# ArchGen 3D Assets & Models Catalog

> Comprehensive 3D Model Catalog, Directory Hierarchy, and Architectural Asset Specification for ArchGen Blender Subsystem and Three.js Visualization.

---

## 1. Overview & Purpose

The **ArchGen 3D Asset Catalog** powers the procedural generation pipeline:
1. **AI Floorplan Generation** (FastAPI Backend + Gemini 2.5 Flash) creates the architectural floorplan layout and room designations.
2. **Procedural Geometry Engine** (Blender 4.x Python Headless) builds walls, slabs, doors, windows, and false ceilings.
3. **Asset Placement & Staging** (`blender/scripts/place_furniture.py`) fetches 3D models and materials according to room type, style, and spatial constraints.
4. **Web 3D Visualization** (React + Three.js / `@react-three/fiber`) loads the exported unified `.glb` scene in real-time.

All 3D assets in this catalog adhere to glTF 2.0 / GLB specifications, standardized real-world meter scaling ($1.0\text{ BU} = 1.0\text{ m}$), bottom-centered pivot points ($Z=0$), and physically-based rendering (PBR Metallic-Roughness).

---

## 2. Directory Hierarchy Map

Below is the organized directory structure created under `blender/assets/`:

```
blender/assets/
│
├── architecture/                   # Architectural components & structural details
│   ├── walls/
│   │   ├── designs/                # 3D wall panels, fluted wood slats, wainscoting
│   │   ├── partitions/             # Glass dividers, wooden screens, metal partitions
│   │   └── trims_baseboards/       # Baseboards, crown moldings, chair rails
│   ├── ceilings/
│   │   ├── designs/                # False ceiling bulkheads, coffered grids, tray ceilings
│   │   ├── beams/                  # Rustic & contemporary exposed ceiling beams
│   │   ├── fans/                   # Modern 3-blade & wooden 5-blade ceiling fans
│   │   └── vents/                  # AC linear slot diffusers, circular grilles
│   ├── doors/                      # Categorized door designs
│   │   ├── interior/               # Modern flush doors, bedroom/bathroom panel doors
│   │   ├── exterior/               # Main pivot doors, security entry doors
│   │   ├── sliding/                # Barn doors, pocket sliding doors, patio glass doors
│   │   └── glass_french/           # Double glazed French doors
│   ├── windows/                    # Categorized window designs
│   │   ├── standard/               # Residential casement & double-hung windows
│   │   ├── floor_to_ceiling/       # Picture windows, curtain wall glass panels
│   │   ├── sliding/                # Horizontal sliding aluminum windows
│   │   └── arched/                 # Arched & clerestory specialty windows
│   ├── stairs/
│   │   ├── straight/               # Floating straight flight stairs, closed riser stairs
│   │   ├── l_shaped/               # L-shaped stairs with intermediate landing
│   │   ├── spiral/                 # Modern spiral steel/wood stairs
│   │   └── railings/               # Glass balustrades, metal handrails, cable railings
│   └── columns/
│       ├── modern/                 # Minimalist square pillars, fluted pillars
│       └── classical/              # Round Doric/Ionic columns, decorative pedestals
│
├── furniture/                      # Room-based furniture models
│   ├── living_room/                # Living room furniture
│   │   ├── sofas/                  # Sectional L-shape, 3-seater, Chesterfield, loveseats
│   │   ├── coffee_tables/          # Marble low tables, nesting round tables, wood tables
│   │   ├── tv_units/               # Low-profile media consoles, floating credenzas
│   │   ├── tv_walls/               # Fluted panel feature walls, marble slab LED backdrops
│   │   ├── armchairs/              # Lounge accent armchairs, swivel club chairs
│   │   ├── side_tables/            # End tables, drink tables, pedestal stands
│   │   └── bookshelves/            # Modular open display shelves, room dividers
│   ├── kitchen/                    # Kitchen furniture & cabinetry
│   │   ├── cabinets_base/          # Lower modular cabinets, drawer units, sink bases
│   │   ├── cabinets_upper/         # Overhead wall cabinets, fluted glass cupboards
│   │   ├── pantries_tall/          # Floor-to-ceiling pantry columns, appliance housings
│   │   ├── islands/                # Freestanding waterfall islands with breakfast bar
│   │   ├── countertops/            # Quartz, granite, and butcher block countertop segments
│   │   └── bar_stools/             # Counter-height stools, swivel bar chairs
│   ├── bathroom/                   # Bathroom furniture & sanitary units
│   │   ├── vanities/               # Single & double basin floating/freestanding vanities
│   │   ├── wash_basins/            # Countertop vessel basins, undermount sinks
│   │   ├── toilets/                # Wall-hung smart toilets, close-coupled commodes
│   │   ├── bathtubs/               # Freestanding oval soaking tubs, corner whirlpools
│   │   ├── showers/                # Frameless glass walk-in shower cabins, trays
│   │   └── storage/                # Mirrored medicine cabinets, tall linen towers
│   ├── bedroom/                    # Bedroom furniture
│   │   ├── beds/                   # King platform beds, upholstered queen beds, canopy beds
│   │   ├── nightstands/            # 2-drawer bedside tables, floating ledges
│   │   ├── wardrobes/              # Sliding mirror closets, walk-in organizer modules
│   │   ├── dressers/               # 6-drawer chests of drawers, tallboy dressers
│   │   └── vanity_tables/          # Makeup vanity tables with mirrors & stools
│   ├── dining_room/                # Dining room furniture
│   │   ├── dining_tables/          # 6/8-seater solid wood tables, round marble tables
│   │   ├── dining_chairs/          # Upholstered fabric chairs, wooden spindle chairs
│   │   ├── sideboards/             # Dining buffet sideboards, china credenzas
│   │   └── bar_units/              # Wine display racks, mobile bar carts, dry bars
│   ├── home_office/                # Study / Home office furniture
│   │   ├── desks/                  # Executive wooden desks, motorized standing desks
│   │   ├── office_chairs/          # Ergonomic mesh task chairs, leather executive chairs
│   │   ├── bookshelves/            # Floor-to-ceiling library shelving, file bookcases
│   │   └── storage/                # Mobile pedestal drawers, lateral filing cabinets
│   ├── entryway/                   # Entryway & Foyer
│   │   ├── consoles/               # Slim accent console tables
│   │   ├── shoe_storage/           # Drop-down shoe cabinets, multi-tier racks
│   │   ├── coat_racks/             # Freestanding coat trees, wall peg rails
│   │   └── benches/                # Upholstered hallway benches, storage benches
│   ├── laundry_room/               # Laundry & Utility room
│   │   ├── cabinets/               # Laundry sink base cabinets, overhead detergent storage
│   │   └── utility_furniture/      # Foldable ironing stations, laundry hamper carts
│   ├── outdoor/                    # Balcony, patio & garden
│   │   ├── lounge_seating/         # All-weather wicker sectionals, sun loungers, daybeds
│   │   ├── dining/                 # Weather-resistant patio tables & chairs
│   │   ├── shading/                # Cantilever sun parasols, pergola frames
│   │   └── planters/               # Architectural concrete planters, garden urns
│   └── kids_room/                  # Children's bedrooms & nursery
│       ├── bunk_beds/              # Twin-over-twin bunk beds, loft study beds
│       ├── toy_storage/            # Modular toy bins, cubby shelving units
│       └── kids_desks/             # Height-adjustable study desks & chairs
│
├── decorations/                    # Accessories & interior staging decor
│   ├── wall_art/                   # Framed abstract prints, canvas oil paintings, posters
│   ├── mirrors/                    # LED backlit vanity mirrors, round brass mirrors, leaning mirrors
│   ├── curtains_blinds/            # Floor-to-ceiling sheer linen drapes, blackout curtains, roller blinds
│   ├── carpets_rugs/               # Large living room area rugs, wool runners, fluffy bedroom mats
│   ├── plants_greenery/            # Potted fiddle-leaf figs, monstera, snake plants, tabletop vases
│   ├── tabletop_decor/             # Ceramic sculptural vases, book stacks, marble trays, candles
│   ├── clocks/                     # Modern minimalist wall clocks, oversized silent quartz clocks
│   └── cushions_throws/            # Velvet throw pillows, bouclé cushions, knitted sofa blankets
│
├── lighting/                       # Lighting fixtures & electrical fittings
│   ├── ceiling_lights/             # Branching chandeliers, glass pendant lights, flush-mount drums
│   ├── recessed_spots/             # Recessed ceiling downlights, gimbal spotlights, track lighting
│   ├── wall_sconces/               # Bedside reading sconces, up/down hallway sconces, vanity bars
│   ├── floor_lamps/                # Arc floor lamps, tripod wood floor lamps, vertical corner LED tubes
│   ├── table_lamps/                # Bedside nightstand lamps, ceramic mushroom lamps, task lamps
│   ├── strip_cove_lights/          # Warm white LED strip profiles, false ceiling cove channels
│   └── switches_sockets/           # Flush modern switch plates, duplex power sockets, wall thermostats
│
├── appliances/                     # Electrical appliances & electronics
│   ├── kitchen/                    # French door fridges, built-in ovens, induction hobs, microwaves, hoods
│   ├── laundry/                    # Front-load washers, heat pump dryers, stacked laundry units
│   └── electronics/                # 65-inch OLED TVs, ultra-slim soundbars, desktop monitors
│
├── fixtures/                       # Plumbing & hardware fixtures
│   ├── plumbing/                   # Gooseneck pull-out faucets, matte black basin mixers, rain shower heads
│   ├── hardware/                   # Lever door handles, cabinet bar pulls, knurled knobs, door stops
│   └── bathroom_accessories/       # Heated towel rails, toilet roll holders, robe hooks, shower caddies
│
└── textures/                       # PBR Material maps & surface finishes
    ├── floors/                     # Hardwood planks, herringbone parquet, light oak, polished marble
    ├── walls/                      # Smooth matte plaster, exposed brick, fluted wood slats, wallpaper
    ├── tiles/                      # Metro subway tiles, ceramic zellige, hexagonal tiles, marble slabs
    ├── ceilings/                   # Smooth white plaster, wooden acoustic slats, ceiling panels
    ├── fabrics/                    # Natural linen, bouclé upholstery, velvet, rug wool, leather
    ├── woods/                      # American walnut, Scandinavian oak, natural teak, mahogany
    ├── stones_marbles/             # Calacatta gold, Carrara white, Nero Marquina black, granite
    ├── metals/                     # Brushed brass, matte black steel, chrome finish, brushed aluminum
    └── grounds/                    # Concrete pavers, lawn grass, gravel stone, patio decking
```

---

## 3. Existing 3D Models Inventory (Current Live Assets)

The repository currently contains **29 3D models** ready for procedural generation and runtime rendering:

| Asset ID | Model Name | Category | Room | Relative File Path | Format | Size | Dimensions ($W \times D \times H$) | Metadata Record |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `entrance_gate_01` | Modern Metal Entrance Gate | `gate` | exterior | `assets/architecture/doors/exterior/Gate.glb` | GLB | 375.0 KB | $4.63 \times 0.17 \times 2.15\text{ m}$ | Exterior site boundary gate |
| `door_standard_01` | Standard Flush Door | `door` | general | `assets/doors/door_standard.glb` | GLB | 41.9 KB | $0.90 \times 0.15 \times 2.10\text{ m}$ | Schema default |
| `door_standard_02` | Panel Interior Door | `door` | general | `assets/doors/door_standard_02.glb` | GLB | 11.0 KB | $0.90 \times 0.15 \times 2.10\text{ m}$ | Schema default |
| `door_standard_03` | Minimalist Door | `door` | general | `assets/doors/door_standard_03.glb` | GLB | 15.4 KB | $0.90 \times 0.15 \times 2.10\text{ m}$ | Schema default |
| `window_standard_01` | Residential Casement Window | `window` | general | `assets/windows/window_standard_01.glb` | GLB | 3.06 MB | $1.20 \times 0.20 \times 1.40\text{ m}$ | Schema default |
| `window_standard_02` | Double Hung Window | `window` | general | `assets/windows/window_standard_02.glb` | GLB | 8.7 KB | $1.00 \times 0.15 \times 1.20\text{ m}$ | Schema default |
| `window_standard_03` | Minimalist Fixed Window | `window` | general | `assets/windows/window_standard_03.glb` | GLB | 8.8 KB | $1.20 \times 0.15 \times 1.20\text{ m}$ | Schema default |
| `living_armchair_01` | Modern Living Lounge Armchair | `armchair` | `living_room` | `assets/furniture/living_room/ArmChair_01.glb` | GLB | 10.34 MB | $0.88 \times 0.88 \times 0.84\text{ m}$ | [`living_armchair_01.json`](file:///d:/Projects/fyp/archigen/blender/metadata/living_armchair_01.json) |
| `coffee_table_01` | Sculptural Low Coffee Table | `coffee_table` | `living_room` | `assets/furniture/living_room/CoffeeTable_01.glb` | GLB | 6.39 MB | $1.10 \times 0.65 \times 0.42\text{ m}$ | [`coffee_table_01.json`](file:///d:/Projects/fyp/archigen/blender/metadata/coffee_table_01.json) |
| `sample_sofa_001` | Contemporary 3-Seater Sofa | `sofa` | `living_room` | `assets/furniture/living_room/Sofa_01_4k.gltf` | glTF | 2.57 KB | $2.20 \times 0.95 \times 0.80\text{ m}$ | [`sample_sofa_001.json`](file:///d:/Projects/fyp/archigen/blender/metadata/sample_sofa_001.json) |
| `floor_lamp_01` | Contemporary Arch Floor Lamp | `lamp` | `living_room` | `assets/furniture/living_room/floor_lamp.glb` | GLB | 29.75 MB | $0.50 \times 0.50 \times 1.85\text{ m}$ | [`floor_lamp_01.json`](file:///d:/Projects/fyp/archigen/blender/metadata/floor_lamp_01.json) |
| `living_tv_cabinet_01` | Media Console & Storage Credenza | `cabinet` | `living_room` | `assets/furniture/living_room/modren_wooden_cabinet_01.glb` | GLB | 29.61 MB | $1.80 \times 0.45 \times 0.60\text{ m}$ | [`living_tv_cabinet_01.json`](file:///d:/Projects/fyp/archigen/blender/metadata/living_tv_cabinet_01.json) |
| `kitchen_cabinet_001` | Modular Overhead Kitchen Cabinet | `cabinet` | `kitchen` | `assets/furniture/kitchen/cabinet_001.glb` | GLB | 10.60 MB | $1.20 \times 0.40 \times 0.80\text{ m}$ | [`kitchen_cabinet_001.json`](file:///d:/Projects/fyp/archigen/blender/metadata/kitchen_cabinet_001.json) |
| `kitchen_island_001` | Modern Marble Top Kitchen Island | `kitchen_counter` | `kitchen` | `assets/furniture/kitchen/kitchen_island_001.glb` | GLB | 846.6 KB | $2.20 \times 1.00 \times 0.92\text{ m}$ | [`kitchen_island_001.json`](file:///d:/Projects/fyp/archigen/blender/metadata/kitchen_island_001.json) |
| `refrigerator_001` | French Door Refrigerator | `refrigerator` | `kitchen` | `assets/furniture/kitchen/refrigerator_001.glb` | GLB | 17.14 MB | $0.92 \times 0.85 \times 1.82\text{ m}$ | [`refrigerator_001.json`](file:///d:/Projects/fyp/archigen/blender/metadata/refrigerator_001.json) |
| `kitchen_sink_001` | Undermount Double Basin Sink | `sink` | `kitchen` | `assets/furniture/kitchen/sink_001.glb` | GLB | 29.22 MB | $0.85 \times 0.55 \times 0.88\text{ m}$ | [`kitchen_sink_001.json`](file:///d:/Projects/fyp/archigen/blender/metadata/kitchen_sink_001.json) |
| `microwave_001` | Retro Countertop Microwave Oven | `stove` | `kitchen` | `assets/furniture/kitchen/vintage_microwave_1.glb` | GLB | 28.64 MB | $0.55 \times 0.42 \times 0.35\text{ m}$ | [`microwave_001.json`](file:///d:/Projects/fyp/archigen/blender/metadata/microwave_001.json) |
| `bathtub_001` | Modern Free-Standing Bathtub | `bathtub` | `bathroom` | `assets/furniture/bathroom/bathtub_001.glb` | GLB | 9.18 MB | $1.75 \times 0.85 \times 0.65\text{ m}$ | [`bathtub_001.json`](file:///d:/Projects/fyp/archigen/blender/metadata/bathtub_001.json) |
| `bathroom_sink_001` | Contemporary Vanity Sink | `sink` | `bathroom` | `assets/furniture/bathroom/sink_001.glb` | GLB | 15.74 MB | $0.90 \times 0.55 \times 0.85\text{ m}$ | [`bathroom_sink_001.json`](file:///d:/Projects/fyp/archigen/blender/metadata/bathroom_sink_001.json) |
| `toilet_001` | Modern Ceramic Toilet | `toilet` | `bathroom` | `assets/furniture/bathroom/toilet_001.glb` | GLB | 834.3 KB | $0.45 \times 0.70 \times 0.80\text{ m}$ | [`toilet_001.json`](file:///d:/Projects/fyp/archigen/blender/metadata/toilet_001.json) |
| `bed_02` | Modern Platform Double Bed | `bed` | `bedroom` | `assets/furniture/bedroom/bed_02.glb` | GLB | 19.96 MB | $2.10 \times 2.20 \times 1.10\text{ m}$ | [`bed_02.json`](file:///d:/Projects/fyp/archigen/blender/metadata/bed_02.json) |
| `bed_gothic_01` | Classic Upholstered Bed | `bed` | `bedroom` | `assets/furniture/bedroom/GothicBed_01.glb` | GLB | 5.40 MB | $1.80 \times 2.10 \times 1.35\text{ m}$ | [`bed_gothic_01.json`](file:///d:/Projects/fyp/archigen/blender/metadata/bed_gothic_01.json) |
| `bedside_table_001` | Minimalist Nightstand | `nightstand` | `bedroom` | `assets/furniture/bedroom/bedside_table_001.glb` | GLB | 12.64 MB | $0.50 \times 0.45 \times 0.55\text{ m}$ | [`bedside_table_001.json`](file:///d:/Projects/fyp/archigen/blender/metadata/bedside_table_001.json) |
| `desk_001` | Modern Executive Study Desk | `desk` | `bedroom` | `assets/furniture/bedroom/desk_001.glb` | GLB | 11.43 MB | $1.40 \times 0.70 \times 0.76\text{ m}$ | [`desk_001.json`](file:///d:/Projects/fyp/archigen/blender/metadata/desk_001.json) |
| `bedroom_cabinet_01` | Modern Wooden Wardrobe Cabinet | `wardrobe` | `bedroom` | `assets/furniture/bedroom/modren_wooden_cabinet_01.glb` | GLB | 29.61 MB | $1.20 \times 0.60 \times 1.95\text{ m}$ | [`bedroom_cabinet_01.json`](file:///d:/Projects/fyp/archigen/blender/metadata/bedroom_cabinet_01.json) |
| `bedroom_armchair_01` | Cozy Accent Armchair | `armchair` | `bedroom` | `assets/furniture/bedroom/ArmChair_01.glb` | GLB | 10.34 MB | $0.85 \times 0.85 \times 0.82\text{ m}$ | [`bedroom_armchair_01.json`](file:///d:/Projects/fyp/archigen/blender/metadata/bedroom_armchair_01.json) |
| `dining_chair_001` | Ergonomic Scandinavian Dining Chair | `chair` | `dining_room` | `assets/furniture/dining_room/dining_chair_001.glb` | GLB | 956.2 KB | $0.50 \times 0.52 \times 0.85\text{ m}$ | [`dining_chair_001.json`](file:///d:/Projects/fyp/archigen/blender/metadata/dining_chair_001.json) |
| `dining_table_001` | Nordic Solid Wood Dining Table | `dining_table` | `dining_room` | `assets/furniture/dining_room/dining_table_001.glb` | GLB | 10.82 MB | $1.80 \times 0.90 \times 0.76\text{ m}$ | [`dining_table_001.json`](file:///d:/Projects/fyp/archigen/blender/metadata/dining_table_001.json) |
| `dining_sideboard_001` | Modern Dining Buffet Sideboard | `cabinet` | `dining_room` | `assets/furniture/dining_room/sideboard_001.glb` | GLB | 10.60 MB | $1.50 \times 0.48 \times 0.85\text{ m}$ | [`dining_sideboard_001.json`](file:///d:/Projects/fyp/archigen/blender/metadata/dining_sideboard_001.json) |

---

## 4. Existing Textures & Materials Inventory

| Texture Identifier | Material Type | Target Surface | Relative File Path | Resolution | Size | Format |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `plaster_wall_diff_2k` | Diffuse / Color | General Walls / Living / Bedroom | `assets/textures/walls/plaster_wall_diff_2k.jpg` | $2048 \times 2048$ | 3.13 MB | JPEG |
| `brick_wall_diff_2k` | Diffuse / Color | Brick Accent Walls / Dining / Loft | `assets/textures/walls/brick_wall_diff_2k.jpg` | $2048 \times 2048$ | 2.04 MB | JPEG |
| `wood_panel_diff_2k` | Diffuse / Color | Wood Slat / Paneling Feature Walls | `assets/textures/walls/wood_panel_diff_2k.jpg` | $2048 \times 2048$ | 998.3 KB | JPEG |
| `dark_wooden_planks_diff_2k` | Diffuse / Color | Floor / Bedroom / Living | `assets/textures/floors/dark_wooden_planks_diff_2k.jpg` | $2048 \times 2048$ | 175.7 KB | JPEG |
| `marble_01_diff_2k` | Diffuse / Color | Floor / Hallway / Kitchen | `assets/textures/floors/marble_01_diff_2k.jpg` | $2048 \times 2048$ | 119.4 KB | JPEG |
| `marble_mosaic_tiles_diff_2k` | Diffuse / Color | Floor / Bathroom / Kitchen | `assets/textures/floors/marble_mosaic_tiles_diff_2k.jpg` | $2048 \times 2048$ | 299.2 KB | JPEG |
| `concrete_pavers_diff_2k` | Diffuse / Color | Ground / Patio / Outdoor | `assets/textures/grounds/concrete_pavers_diff_2k.jpg` | $2048 \times 2048$ | 200.0 KB | JPEG |
| `leafy_grass_diff_1k` | Diffuse / Color | Ground / Lawn / Garden | `assets/textures/grounds/leafy_grass_diff_1k.jpg` | $1024 \times 1024$ | 374.0 KB | JPEG |

---

## 5. Comprehensive Specification of Required Models by Room & Category

Below is the exhaustive specification of all items to be placed, procedurally built, or populated from the 3D catalog:

### 5.1 Room 1: Living Room

| Element | Target Category / Folder | Recommended Standard Dimensions ($W \times D \times H$) | Description / Modeling Specifications |
| :--- | :--- | :--- | :--- |
| **Walls** | `architecture/walls/` | Thickness: $0.15 - 0.20\text{ m}$, Height: $3.00\text{ m}$ | Procedural wall mesh generated by `generate_house.py`. |
| **Wall Texture** | `textures/walls/` | Seamless $2\text{k}$ tiling | Matte white plaster, warm greige, exposed brick, or acoustic wood slat texture. |
| **Wall Feature / Design** | `architecture/walls/designs/` | $2.80 \times 0.05 \times 2.80\text{ m}$ | 3D acoustic fluted wood slat accent paneling, wainscoting panel molds. |
| **Floor** | `textures/floors/` | Seamless $2\text{k}$ tiling | Oak hardwood planks, herringbone parquet, or polished stone. |
| **Ceiling** | `architecture/ceilings/designs/` | Depth: $0.12\text{ m}$ drop | False ceiling perimeter bulkhead with recessed LED cove lighting channel. |
| **Ceiling Fan** | `architecture/ceilings/fans/` | $\varnothing 1.30\text{ m}$, Drop: $0.35\text{ m}$ | Contemporary 3-blade matte black / walnut ceiling fan with integrated LED light. |
| **Doors** | `architecture/doors/interior/` | $0.90 \times 0.15 \times 2.10\text{ m}$ | Flush wooden interior door with minimalist lever handle. |
| **Windows** | `architecture/windows/floor_to_ceiling/` | $2.40 \times 0.15 \times 2.40\text{ m}$ | Floor-to-ceiling panoramic picture window with dark aluminum frames. |
| **Sofa** | `furniture/living_room/sofas/` | $2.40 \times 1.60 \times 0.82\text{ m}$ | Sectional L-shaped upholstered fabric couch with plush cushions. |
| **Coffee Table** | `furniture/living_room/coffee_tables/` | $1.20 \times 0.65 \times 0.42\text{ m}$ | Low-profile marble top coffee table with black steel or oak legs. |
| **Armchair** | `furniture/living_room/armchairs/` | $0.85 \times 0.85 \times 0.82\text{ m}$ | Accent lounge chair in bouclé or leather with wooden legs. |
| **TV** | `appliances/electronics/` | $1.45 \times 0.06 \times 0.85\text{ m}$ | 65-inch Ultra-thin OLED 4K television with wall mount bracket. |
| **TV Wall / Backdrop** | `furniture/living_room/tv_walls/` | $2.60 \times 0.08 \times 2.80\text{ m}$ | Sintered stone / marble slab backplate with vertical fluted wood slat side panels. |
| **TV Console** | `furniture/living_room/tv_units/` | $2.00 \times 0.45 \times 0.50\text{ m}$ | Low-profile floating or ground credenza with slatted cabinet doors. |
| **Chandelier / Pendant** | `lighting/ceiling_lights/` | $\varnothing 0.80\text{ m}$, Drop: $0.60\text{ m}$ | Modern Nordic branching molecular chandelier with frosted glass globes. |
| **Floor Lamp** | `lighting/floor_lamps/` | $0.50 \times 0.50 \times 1.85\text{ m}$ | Arched standing brass/black lamp or tripod floor lamp with linen shade. |
| **Cove Lighting** | `lighting/strip_cove_lights/` | Strip width: $0.02\text{ m}$ | $3000\text{K}$ warm white indirect LED cove light channel along ceiling borders. |
| **Curtains** | `decorations/curtains_blinds/` | Width: $2.60\text{ m}$, Height: $2.90\text{ m}$ | Floor-to-ceiling double track drapes: sheer white inner linen + blackout velvet outer. |
| **Carpet / Area Rug** | `decorations/carpets_rugs/` | $3.00 \times 2.00 \times 0.015\text{ m}$ | High-density Scandinavian woven geometric wool area rug. |
| **Wall Art** | `decorations/wall_art/` | $0.90 \times 0.04 \times 1.20\text{ m}$ | Framed minimalist abstract oil canvas with thin black aluminum frame. |
| **Indoor Plants** | `decorations/plants_greenery/` | $\varnothing 0.45\text{ m}$, Height: $1.60\text{ m}$ | Tall potted Fiddle Leaf Fig (*Ficus lyrata*) or Monstera in white ceramic planter. |
| **Tabletop Decor** | `decorations/tabletop_decor/` | Various ($0.15 - 0.35\text{ m}$) | Organic ceramic vases, decorative hardcover art book stack, scented candle tray. |

---

### 5.2 Room 2: Kitchen

| Element | Target Category / Folder | Recommended Standard Dimensions ($W \times D \times H$) | Description / Modeling Specifications |
| :--- | :--- | :--- | :--- |
| **Kitchen Walls** | `architecture/walls/` | Thickness: $0.15\text{ m}$, Height: $3.00\text{ m}$ | Perimeter walls with dedicated plumbing & electrical cutouts. |
| **Backsplash Tiles** | `textures/tiles/` | Tile module: $0.075 \times 0.15\text{ m}$ | Glossy white subway metro tiles with dark grout, or slab quartz backsplash. |
| **Flooring Tiles** | `textures/floors/` | $0.60 \times 0.60\text{ m}$ or $0.60 \times 1.20\text{ m}$ | Large format anti-slip porcelain or honed terrazzo floor tiles. |
| **Base Cabinets** | `furniture/kitchen/cabinets_base/` | $0.60\text{ m}$ depth, $0.86\text{ m}$ height | Modular drawer units, soft-close Blum hinges, matte lacquered flat fronts. |
| **Upper Cabinets** | `furniture/kitchen/cabinets_upper/` | $0.35\text{ m}$ depth, $0.80\text{ m}$ height | Overhead cupboards with integrated bottom LED channel and push-to-open doors. |
| **Tall Pantry Tower** | `furniture/kitchen/pantries_tall/` | $0.60 \times 0.60 \times 2.40\text{ m}$ | Integrated column housing wall oven, microwave, and pull-out larder racks. |
| **Countertop** | `furniture/kitchen/countertops/` | $0.65\text{ m}$ depth, $0.04\text{ m}$ thickness | Calacatta Gold engineered quartz with bullnose or mitered edge profile. |
| **Kitchen Island** | `furniture/kitchen/islands/` | $2.40 \times 1.00 \times 0.92\text{ m}$ | Freestanding kitchen island with waterfall marble ends & recessed breakfast counter. |
| **Bar Stools** | `furniture/kitchen/bar_stools/` | $0.45 \times 0.45 \times 0.75\text{ m}$ | Counter-height upholstered minimalist bar stools with footrest. |
| **Refrigerator** | `appliances/kitchen/` | $0.92 \times 0.85 \times 1.82\text{ m}$ | Stainless steel French-door refrigerator with exterior water dispenser. |
| **Oven** | `appliances/kitchen/` | $0.60 \times 0.58 \times 0.60\text{ m}$ | Built-in convection electric wall oven with digital touch screen. |
| **Cooktop** | `appliances/kitchen/` | $0.80 \times 0.52 \times 0.06\text{ m}$ | 4-zone flush induction glass ceramic cooktop. |
| **Range Hood** | `appliances/kitchen/` | $0.90 \times 0.50 \times 0.70\text{ m}$ | Stainless steel / matte black chimney extractor hood with LED task lights. |
| **Microwave** | `appliances/kitchen/` | $0.55 \times 0.42 \times 0.35\text{ m}$ | Built-in or countertop microwave oven with stainless steel trim kit. |
| **Dishwasher** | `appliances/kitchen/` | $0.60 \times 0.60 \times 0.85\text{ m}$ | Fully integrated front panel dishwasher matching cabinet front. |
| **Sink** | `furniture/kitchen/sink_001.glb` | $0.85 \times 0.55 \times 0.88\text{ m}$ | Undermount double basin stainless steel / granite composite sink. |
| **Faucet / Tap** | `fixtures/plumbing/` | $0.22 \times 0.10 \times 0.42\text{ m}$ | High-arch gooseneck pull-down commercial sprayer faucet in matte black. |
| **Island Pendants** | `lighting/ceiling_lights/` | $\varnothing 0.25\text{ m}$, Drop: $0.80\text{ m}$ | Trio of conical smoked glass or brushed brass mini pendant lights. |
| **Under-Cabinet Lights** | `lighting/strip_cove_lights/` | Width: $0.015\text{ m}$ | Continuous surface-mounted diffuser channel with $4000\text{K}$ neutral white LEDs. |

---

### 5.3 Room 3: Bathroom

| Element | Target Category / Folder | Recommended Standard Dimensions ($W \times D \times H$) | Description / Modeling Specifications |
| :--- | :--- | :--- | :--- |
| **Toilet** | `furniture/bathroom/toilets/` | $0.40 \times 0.56 \times 0.42\text{ m}$ | Wall-hung rimless toilet bowl with dual flush wall plate and concealed tank. |
| **Wash Basin / Vanity** | `furniture/bathroom/vanities/` | $1.20 \times 0.52 \times 0.55\text{ m}$ | Wall-mounted floating walnut vanity with white ceramic vessel sink. |
| **Basin Mixer Tap** | `fixtures/plumbing/` | $0.05 \times 0.16 \times 0.28\text{ m}$ | Single-lever tall vessel mixer tap in electroplated matte black or brushed gold. |
| **Shower Enclosure** | `furniture/bathroom/showers/` | $1.00 \times 1.00 \times 2.10\text{ m}$ | Frameless $10\text{ mm}$ tempered glass walk-in shower panel with black stabilizing bar. |
| **Shower System** | `fixtures/plumbing/` | $0.40 \times 0.12 \times 1.20\text{ m}$ | Thermostatic shower column with $300\text{ mm}$ ceiling rain shower head and handheld wand. |
| **Bathtub** | `furniture/bathroom/bathtubs/` | $1.75 \times 0.85 \times 0.65\text{ m}$ | Freestanding ergonomic oval acrylic soaking bathtub with floor-mounted tub filler. |
| **Wall Tiles** | `textures/tiles/` | $0.30 \times 0.60\text{ m}$ or slabs | White Carrara marble tile texture or vertical handmade Japanese finger tiles. |
| **Floor Tiles** | `textures/tiles/` | $0.60 \times 0.60\text{ m}$ | Textured slip-resistant graphite grey slate or terrazzo floor tiles. |
| **Mirror** | `decorations/mirrors/` | $\varnothing 0.80\text{ m}$ or $0.80 \times 1.00\text{ m}$ | Smart LED backlit anti-fog mirror with touch sensor and warm front wash. |
| **Vanity Lighting** | `lighting/wall_sconces/` | $0.60 \times 0.08 \times 0.06\text{ m}$ | Horizontal linear LED vanity light bar mounted above the mirror ($3000\text{K}$). |
| **Shower / Ceiling Spot** | `lighting/recessed_spots/` | $\varnothing 0.09\text{ m}$, Cutout: $0.075\text{ m}$ | IP65 waterproof recessed LED downlights for wet areas. |
| **Towel Warmer** | `fixtures/bathroom_accessories/` | $0.50 \times 0.10 \times 1.00\text{ m}$ | Electric heated ladder towel rail in matte black finish. |
| **Bath Accessories** | `fixtures/bathroom_accessories/` | Various | Minimalist toilet roll holder, double robe hooks, recessed wall shower niche. |

---

### 5.4 Room 4: Bedroom

| Element | Target Category / Folder | Recommended Standard Dimensions ($W \times D \times H$) | Description / Modeling Specifications |
| :--- | :--- | :--- | :--- |
| **Bed** | `furniture/bedroom/beds/` | $2.00 \times 2.20 \times 1.10\text{ m}$ | King platform bed with upholstered padded fabric headboard & memory foam mattress. |
| **Nightstands** | `furniture/bedroom/nightstands/` | $0.50 \times 0.45 \times 0.55\text{ m}$ | Pair of matching 2-drawer bedside tables with soft-close wood drawers. |
| **Wardrobe / Closet** | `furniture/bedroom/wardrobes/` | $2.40 \times 0.65 \times 2.40\text{ m}$ | 3-door sliding wardrobe with tinted glass doors and internal LED hangers. |
| **Dresser / Chest** | `furniture/bedroom/dressers/` | $1.40 \times 0.48 \times 0.85\text{ m}$ | 6-drawer low dresser with fluted wood drawers and minimalist handles. |
| **Vanity Table** | `furniture/bedroom/vanity_tables/` | $1.00 \times 0.45 \times 0.76\text{ m}$ | Dressing table with flip-up vanity mirror, jewelry divider, and cushioned stool. |
| **Bedside Lamps** | `lighting/table_lamps/` | $\varnothing 0.28\text{ m}$, Height: $0.45\text{ m}$ | Minimalist ceramic table lamps with warm linen drum shades. |
| **Pendant / Chandelier** | `lighting/ceiling_lights/` | $\varnothing 0.60\text{ m}$, Drop: $0.45\text{ m}$ | Modern fabric drum flush mount or delicate paper pendant chandelier. |
| **Rug** | `decorations/carpets_rugs/` | $2.40 \times 1.80 \times 0.02\text{ m}$ | Ultra-soft plush bedside runner rug or under-bed accent wool carpet. |
| **Blackout Curtains** | `decorations/curtains_blinds/` | Width: $2.40\text{ m}$, Height: $2.90\text{ m}$ | Full acoustic blackout floor-length curtains. |

---

### 5.5 Room 5: Dining Room

| Element | Target Category / Folder | Recommended Standard Dimensions ($W \times D \times H$) | Description / Modeling Specifications |
| :--- | :--- | :--- | :--- |
| **Dining Table** | `furniture/dining_room/dining_tables/` | $2.00 \times 0.95 \times 0.76\text{ m}$ | 6 to 8-seater solid French oak or sintered stone top dining table. |
| **Dining Chairs** | `furniture/dining_room/dining_chairs/` | $0.52 \times 0.55 \times 0.84\text{ m}$ | Set of 6 ergonomic curved back dining chairs with bouclé upholstery. |
| **Sideboard / Buffet** | `furniture/dining_room/sideboards/` | $1.80 \times 0.48 \times 0.82\text{ m}$ | 4-door buffet credenza with brass hardware for dinnerware storage. |
| **Bar Cabinet / Cart** | `furniture/dining_room/bar_units/` | $0.80 \times 0.45 \times 0.90\text{ m}$ | Brass 2-tier rolling bar cart with stemware rack and wine bottle slots. |
| **Dining Chandelier** | `lighting/ceiling_lights/` | $1.20 \times 0.35\text{ m}$, Drop: $0.70\text{ m}$ | Horizontal linear LED dining chandelier with diffuser bar over table. |
| **Wall Mirror** | `decorations/mirrors/` | $1.00 \times 0.04 \times 1.40\text{ m}$ | Oversized arched brass leaner mirror placed above the sideboard. |

---

### 5.6 Room 6: Home Office / Study

| Element | Target Category / Folder | Recommended Standard Dimensions ($W \times D \times H$) | Description / Modeling Specifications |
| :--- | :--- | :--- | :--- |
| **Executive Desk** | `furniture/home_office/desks/` | $1.60 \times 0.80 \times 0.75\text{ m}$ | Dual-motor electric standing desk with solid walnut desktop and cable tray. |
| **Office Chair** | `furniture/home_office/office_chairs/` | $0.65 \times 0.65 \times 1.05\text{ m}$ | High-performance ergonomic mesh task chair with 3D armrests & lumbar support. |
| **Bookcase / Shelves** | `furniture/home_office/bookshelves/` | $1.80 \times 0.35 \times 2.20\text{ m}$ | Floor-to-ceiling modular library shelving with lower closed cabinets. |
| **Desk Task Lamp** | `lighting/table_lamps/` | $0.40 \times 0.18 \times 0.45\text{ m}$ | Articulated architect balance-arm LED desk lamp with dimmable control. |
| **Computer Monitor** | `appliances/electronics/` | $0.81 \times 0.22 \times 0.52\text{ m}$ | 34-inch ultra-wide curved monitor on minimalist monitor arm. |

---

### 5.7 Room 7: Entryway & Foyer

| Element | Target Category / Folder | Recommended Standard Dimensions ($W \times D \times H$) | Description / Modeling Specifications |
| :--- | :--- | :--- | :--- |
| **Console Table** | `furniture/entryway/consoles/` | $1.20 \times 0.35 \times 0.85\text{ m}$ | Slim entryway console with sintered stone top and fluted base. |
| **Shoe Cabinet** | `furniture/entryway/shoe_storage/` | $0.90 \times 0.30 \times 1.10\text{ m}$ | 3-tier drop-down shoe storage unit accommodating up to 18 pairs. |
| **Coat Rack / Tree** | `furniture/entryway/coat_racks/` | $\varnothing 0.40\text{ m}$, Height: $1.75\text{ m}$ | Freestanding Scandinavian wooden coat tree or wall hook rail. |
| **Entryway Bench** | `furniture/entryway/benches/` | $1.00 \times 0.40 \times 0.45\text{ m}$ | Upholstered hallway bench with bottom shelf for shoe placement. |
| **Round Wall Mirror** | `decorations/mirrors/` | $\varnothing 0.90\text{ m}$, Depth: $0.03\text{ m}$ | Statement round gold mirror centered above the console table. |

---

### 5.8 Room 8: Laundry & Utility

| Element | Target Category / Folder | Recommended Standard Dimensions ($W \times D \times H$) | Description / Modeling Specifications |
| :--- | :--- | :--- | :--- |
| **Washing Machine** | `appliances/laundry/` | $0.60 \times 0.65 \times 0.85\text{ m}$ | Front-loading $10\text{ kg}$ smart inverter washing machine in dark stainless. |
| **Tumble Dryer** | `appliances/laundry/` | $0.60 \times 0.65 \times 0.85\text{ m}$ | Heat-pump condenser dryer stacked or side-by-side with washer. |
| **Utility Sink** | `fixtures/plumbing/` | $0.55 \times 0.50 \times 0.88\text{ m}$ | Deep stainless utility laundry basin with pull-out mixer. |
| **Overhead Cabinets** | `furniture/laundry_room/cabinets/` | $1.20 \times 0.35 \times 0.70\text{ m}$ | Upper cabinets with dedicated detergent racks and folded towel shelves. |
| **Laundry Hamper** | `furniture/laundry_room/utility_furniture/` | $0.45 \times 0.40 \times 0.75\text{ m}$ | Pull-out dual-compartment laundry sorter hamper. |

---

### 5.9 Room 9: Outdoor, Patio & Garden

| Element | Target Category / Folder | Recommended Standard Dimensions ($W \times D \times H$) | Description / Modeling Specifications |
| :--- | :--- | :--- | :--- |
| **Outdoor Lounge Set** | `furniture/outdoor/lounge_seating/` | $2.20 \times 1.50 \times 0.75\text{ m}$ | All-weather aluminum & synthetic wicker L-sofa with water-repellent cushions. |
| **Patio Dining Table** | `furniture/outdoor/dining/` | $1.60 \times 0.90 \times 0.75\text{ m}$ | Teak wood slatted outdoor dining table with weather-sealed frame. |
| **Sun Lounger** | `furniture/outdoor/lounge_seating/` | $1.95 \times 0.68 \times 0.35\text{ m}$ | Multi-position reclining sunbed lounger with wheels. |
| **Cantilever Parasol** | `furniture/outdoor/shading/` | $\varnothing 3.00\text{ m}$, Height: $2.60\text{ m}$ | Heavy-duty cantilever 360-degree rotating garden parasol umbrella with granite base. |
| **Planters** | `furniture/outdoor/planters/` | $\varnothing 0.50\text{ m}$, Height: $0.75\text{ m}$ | Architectural cast concrete cylindrical outdoor urn planters. |

---

## 6. Technical 3D Asset Guidelines & Pipeline Standards

### 6.1 Coordinate System & Scale
- **Blender Unit**: $1.0\text{ BU} = 1.0\text{ Meter}$.
- **Up Axis**: $+Z$ is World Up. Forward is $-Y$.
- **Pivot Origin**: Centered horizontally at $(X=0, Y=0)$ with base sitting at the floor plane ($Z = 0.0$). This ensures direct, glitch-free floor snapping without collision sinking.

### 6.2 Polygon Budgets (Three.js Web Optimization)
| Asset Tier | Target Triangle Count | Recommended Draw Calls | Usage |
| :--- | :--- | :--- | :--- |
| **Tier 1 (Small / Accessory)** | $500 - 3,000$ tris | 1 material / 1 draw call | Cutlery, small decor, door handles, light switches, switches |
| **Tier 2 (Standard Furniture)** | $3,000 - 15,000$ tris | 1 - 2 materials | Dining chairs, nightstands, coffee tables, toilets, lamps |
| **Tier 3 (Focal / Complex)** | $15,000 - 35,000$ tris | 2 - 3 materials | Sectional sofas, chandeliers, bathtubs, beds with detailed fabric wrinkles |
| **Tier 4 (Structural / Walls)** | Procedural low poly | 1 material per surface | Walls, slabs, ceiling bulkheads |

### 6.3 Material & Texture Specifications
- **PBR Standard**: Khronos glTF 2.0 Metallic-Roughness workflow.
- **Embedded vs External**: All textures must be packed directly inside the `.glb` binary file.
- **Texture Dimensions**: Square powers-of-two ($1024 \times 1024$ or $2048 \times 2048$).
- **Color Spaces**:
  - Base Color / Diffuse: **sRGB**
  - Roughness / Metallic / Ambient Occlusion: **Linear Non-Color**
  - Normal Map: **Linear Non-Color** (OpenGL $+Y$ format)

---

## 7. Adding New Assets to Catalog

### Step 1: Place 3D Model in Folder
Save the optimized `.glb` file in the corresponding folder:
```
blender/assets/furniture/living_room/sofas/modern_boucle_sofa_001.glb
```

### Step 2: Create JSON Metadata Record
Create a JSON file in `blender/metadata/modern_boucle_sofa_001.json` validating against `furniture.schema.json`:
```json
{
  "id": "modern_boucle_sofa_001",
  "name": "Contemporary Boucle Sectional Sofa",
  "category": "sofa",
  "room": "living_room",
  "style": ["modern", "minimalist", "scandinavian"],
  "width": 2.60,
  "depth": 1.65,
  "height": 0.82,
  "model_file": "assets/furniture/living_room/sofas/modern_boucle_sofa_001.glb",
  "format": "glb",
  "license": "CC0",
  "source": "Poly Haven",
  "source_url": "https://polyhaven.com",
  "tags": ["sofa", "sectional", "living room", "boucle", "couch", "seating"]
}
```

### Step 3: Run Catalog Rebuild & S3 Sync
```powershell
# Rebuild metadata index
& "d:\Projects\fyp\archigen\backend\.venv\Scripts\python.exe" blender/scripts/generate_metadata.py

# Sync updated assets to cloud storage (optional)
& "d:\Projects\fyp\archigen\backend\.venv\Scripts\python.exe" blender/scripts/sync_s3_assets.py --direction upload --bucket my-archigen-storage
```
