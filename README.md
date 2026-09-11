# Geospatial Data Engineering Pipeline for Urban Infrastructure Analysis in Abuja, Nigeria

## Problem Statement

Urban infrastructure data for Nigerian cities is fragmented, inconsistently
formatted, and rarely delivered in a state that's directly usable for
analysis. OpenStreetMap holds a genuinely rich record of Abuja's roads and
buildings, but raw OSM exports are messy: inconsistent tagging, mixed
geometry types, multi-value fields, and no spatial indexing. This project
builds a reproducible pipeline that takes that raw data and turns it into
clean, validated, query-ready tables in a spatial database.

## Why This Project Matters

This project exists specifically to demonstrate **data engineering**
skills - acquiring, validating, cleaning, transforming, and loading real
spatial data into a production-style database - as a complement to my
existing GIS, remote sensing, and machine learning portfolio work. It's
the layer that sits underneath any spatial analysis or geospatial AI
project: without a reliable pipeline turning raw data into trustworthy
tables, none of the analysis on top of it can be trusted either.

## Project Architecture
OpenStreetMap (via OSMnx / Overpass API)
↓
Raw Data (data/raw/) - untouched OSM pulls
↓
Python Ingestion (01_ingest.py)
↓
Validation (02_validate.py) - honest before-cleaning snapshot
↓
Cleaning (03_clean.py) - geometry fixes, dedup, type standardization
↓
Geospatial Transformation - reprojection, derived fields (length, area)
↓
PostgreSQL + PostGIS (04_load_postgis.py) - staging schema, spatial indexes
↓
SQL/PostGIS Transformation (transformations.sql) - analytics schema
↓
Analytics Tables - road_summary, building_summary, building_road_proximity
↓
Data Quality Report (05_quality_report.py) - outputs/data_quality_report.csv


## Data Source

**OpenStreetMap**, accessed via the [OSMnx](https://osmnx.readthedocs.io/)
Python library, which queries the Overpass API directly.

The pipeline pulls two datasets for a bounding box covering central Abuja
(Wuse, Garki, Maitama, Asokoro, and the Central Business District):

- **Roads** - the drivable road network (`network_type="drive"`)
- **Buildings** - all tagged building footprints (`building=*`)

**Why a bounding box instead of an administrative boundary:** the initial
approach used named administrative areas (first the full Federal Capital
Territory, then Abuja Municipal Area Council). The full FCT query was too
large for OSM's public Overpass server to reliably return in one request,
and the AMAC administrative polygon wasn't cleanly resolvable via OSM's
geocoder. A bounding box (`7.40, 9.00, 7.55, 9.12`) sidesteps both
problems: it's predictable, reproducible, and gives direct control over
how much data is pulled - a deliberate scoping decision made explicitly
for the "extreme ease, laptop-friendly" goal of this project, not an
accident.

**Why only two datasets:** roads and buildings are sufficient to
demonstrate the full pipeline end to end, including two different
geometry types (LineString vs Polygon/MultiPolygon), two different
PostGIS measurement functions (`ST_Length` vs `ST_Area`), and one
genuine cross-dataset spatial question (building proximity to roads).
Adding more datasets (schools, hospitals, markets) would not have added
proportional value to the data engineering demonstration.

Raw files are **not** committed to this repository (~13MB roads,
~190MB buildings) - they're excluded via `.gitignore` and can be
regenerated at any time by running `01_ingest.py`.

## Technologies

- **Python** - Pandas, GeoPandas, Shapely, OSMnx
- **PostgreSQL + PostGIS** - spatial database, run via Docker for
  consistent, reproducible setup across machines
- **SQL** - schema definition and analytical transformations
- **SQLAlchemy + psycopg2 + GeoAlchemy2** - Python-to-PostGIS connectivity
- **Docker / Docker Compose** - used solely to run PostgreSQL/PostGIS
  consistently; no other part of this pipeline uses Docker
- **Git / GitHub** - version control

## Pipeline Stages

| Script | Stage | What it does |
|---|---|---|
| `01_ingest.py` | Ingestion | Pulls raw roads and buildings from OSM via OSMnx, saves untouched to `data/raw/` |
| `02_validate.py` | Validation | Reports null/invalid geometries, duplicates, geometry types, CRS - no fixing, only reporting |
| `03_clean.py` | Cleaning + Transformation | Flattens multi-value OSM tag columns, fixes invalid geometries, standardizes building geometry type, reprojects to a metric CRS, calculates derived fields (length, area), saves to `data/processed/` |
| `04_load_postgis.py` | Load | Loads cleaned GeoDataFrames into PostGIS `staging` tables |
| `05_quality_report.py` | Quality Reporting | Queries raw files, processed files, and the live database to generate `outputs/data_quality_report.csv` |

SQL transformations (`sql/transformations.sql`) run separately, building
the `analytics` schema from `staging` using PostGIS spatial functions.

## Database Design

Two schemas are used:

- **`staging`** - `cleaned_roads`, `cleaned_buildings`. Holds cleaned,
  validated data loaded directly from Python. This is the source of
  truth for everything downstream.
- **`analytics`** - `road_summary`, `building_summary`,
  `building_road_proximity`. Derived, query-ready tables built entirely
  in SQL from `staging`.

A separate `raw` schema inside the database was deliberately **not**
created. The untouched raw files already live in `data/raw/` on disk;
loading unmodified OSM data into Postgres as well would duplicate that
without adding value. The `staging` schema is the first point where the
database holds meaningful, validated data.

Both `staging` tables have a `GIST` spatial index on their geometry
column - this is what makes the `ST_DWithin`/`ST_Intersects` proximity
query in the analytics layer fast, rather than a full table scan on
every comparison.

## Data Cleaning

Performed in `03_clean.py`:

- **Multi-value tag flattening** - some OSM tag columns (e.g. `highway`)
  can hold multiple values for a single feature. Depending on the read
  path, these appeared as real Python lists, NumPy arrays, or (after a
  round trip through GeoJSON) strings that merely looked like lists
  (e.g. `"['residential']"`). All three cases are detected and flattened
  to a single value.
- **Invalid geometry fixing** - any invalid geometry is repaired using
  Shapely's `make_valid` (the code-level equivalent of PostGIS's
  `ST_MakeValid`), even though the validation step found none in this
  particular pull - this keeps the pipeline robust against future OSM
  data that may not be as clean.
- **Geometry type standardization** - the raw buildings pull included 7
  Point-only records (no polygon outline) among 61,847 polygons; these
  were dropped, since they can't produce an area measurement. All
  remaining building geometries are normalized to MultiPolygon, since
  `make_valid` can turn a Polygon into a MultiPolygon when repairing a
  self-intersection, and PostGIS enforces one consistent geometry type
  per column.
- **CRS reprojection** - raw data is in EPSG:4326 (degrees), unsuitable
  for measuring length or area. Cleaned data is reprojected to
  EPSG:32632 (UTM Zone 32N), the correct metric CRS for this longitude
  band.
- **Duplicate detection** - exact duplicate rows are dropped.
- **Column pruning** - only a small set of useful columns is kept,
  rather than every sparse OSM tag.

**Record counts:**

| Dataset | Before Cleaning | After Cleaning | Loaded into Database |
|---|---|---|---|
| Roads | 26,111 | 26,111 | 26,111 |
| Buildings | 61,854 | 61,847 | 61,847 |

Roads required no record removal - the raw pull had zero nulls, zero
invalid geometries, and zero duplicates. Buildings lost 7 records, all
Point-only geometries with no polygon shape to measure.

## Data Quality Checks

`02_validate.py` and `05_quality_report.py` together check: total
records, null geometries, invalid geometries, duplicate rows, geometry
type distribution, and CRS - on both raw and cleaned data, plus final
loaded counts from the live database. All numbers are generated by
code and written to `outputs/data_quality_report.csv`; none are
hand-typed.

## PostGIS Operations

| Function | Used for |
|---|---|
| `ST_Transform` (via GeoPandas `to_crs`) | Reprojecting from EPSG:4326 to EPSG:32632 |
| `ST_MakeValid` (via Shapely `make_valid`) | Repairing invalid geometries |
| `ST_Length` | Calculating road segment length in metres |
| `ST_Area` | Calculating building footprint area in square metres |
| `ST_DWithin` | Finding buildings within 200m of a road (index-assisted candidate search), then flagging buildings within 50m specifically |
| `ST_Distance` | Calculating exact distance from each building to its nearest road |
| `GIST` index | Spatial indexing on both staging tables, enabling fast proximity queries |

`ST_Intersects` and `ST_Contains` were considered but not used - the
proximity question this dataset actually supports is "how close is this
building to a road," which is a distance question, not a containment or
overlap question. Functions were chosen to fit the data, not to
pad the list.

## Results

- **26,111** road segments mapped, totalling approximately
  **3,494 km** of road length across central Abuja
- **61,847** cleaned building footprints, totalling approximately
  **14.9 million m²** of building area
- **13** distinct road types identified (residential dominates at
  ~2,402 km of the total, consistent with a dense urban street network)
- **97.8%** of buildings (60,511 of 61,847) are within 200m of a mapped
  road; the remaining ~2.2% likely reflects genuine gaps in road
  mapping coverage at the edges of the bounding box, or buildings set
  back from any drivable road
- Building type tagging is dominated by the generic `building=yes` tag
  (60,274 of 61,847 records) - this is a known, common characteristic
  of OSM data, not a cleaning failure. Only a minority of contributors
  specify a building subtype.

## Project Structure
geospatial-data-engineering-abuja/
│
├── data/
│ ├── raw/ # untouched OSM pulls (gitignored)
│ └── processed/ # cleaned, transformed data (gitignored)
│
├── src/
│ ├── 01_ingest.py
│ ├── 02_validate.py
│ ├── 03_clean.py
│ ├── 04_load_postgis.py
│ └── 05_quality_report.py
│
├── sql/
│ ├── schema.sql
│ └── transformations.sql
│
├── outputs/
│ └── data_quality_report.csv
│
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md


## Installation

**Prerequisites:** Python 3.10+, Docker Desktop, Git.

```bash
git clone https://github.com/lekejr/geospatial-data-engineering-abuja.git
cd geospatial-data-engineering-abuja

python -m venv venv
# Windows:
.\venv\Scripts\Activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env with your own local database credentials
```

## How to Run

```bash
# 1. Start PostgreSQL/PostGIS
docker compose up -d

# 2. Create the database schema
Get-Content sql\schema.sql | docker exec -i abuja_geodb psql -U <DB_USER> -d <DB_NAME>
# (macOS/Linux: cat sql/schema.sql | docker exec -i abuja_geodb psql -U <DB_USER> -d <DB_NAME>)

# 3. Run the pipeline in order
python src/01_ingest.py
python src/02_validate.py
python src/03_clean.py
python src/04_load_postgis.py

# 4. Build the analytics tables
Get-Content sql\transformations.sql | docker exec -i abuja_geodb psql -U <DB_USER> -d <DB_NAME>

# 5. Generate the data quality report
python src/05_quality_report.py
```

## Limitations

- Scoped to a bounding box over central Abuja, not the full FCT - a
  deliberate trade-off for reproducibility and laptop-friendliness, not
  full administrative coverage.
- OSM data quality depends entirely on volunteer contributions;
  building subtype tagging in particular is sparse (`building=yes`
  dominates).
- The proximity analysis measures straight-line distance to the nearest
  road, not actual travel distance along the road network.
- No automated testing framework (e.g. pytest/Great Expectations) is
  included; data quality is checked via dedicated scripts rather than a
  formal testing suite.

## Lessons Learned / Debugging Notes

A few genuine issues came up while building this pipeline, worth noting
because they reflect real data engineering problem-solving rather than a
clean, uneventful build:

- **Infrastructure setup**: Docker Desktop initially failed with a
  virtualization error despite hardware virtualization being enabled in
  BIOS - the actual cause was that Windows Subsystem for Linux and the
  Virtual Machine Platform features weren't enabled at the OS level.
  Enabling both and updating WSL2 resolved it.
- **Port conflict**: after fixing Docker, database loads failed with a
  password authentication error even though credentials were correct.
  The cause was a separate, pre-existing native PostgreSQL service
  already running on the machine and occupying port 5432, silently
  intercepting connections meant for the Docker container. Stopping the
  native service resolved it.
- **Multi-value OSM tags**: a `highway` column containing multiple
  tag values per feature was serialized differently depending on the
  read path - as a Python list, a NumPy array, or a GeoJSON round-tripped
  string like `"['residential']"`. All three needed explicit handling to
  avoid corrupting the `road_summary` analytics table with duplicate,
  malformed category labels.
- **Geometry type mismatch on load**: `make_valid()` occasionally
  converts a slightly invalid Polygon into a MultiPolygon while
  repairing it, which PostGIS rejects if the target column is typed
  strictly as `Polygon`. Standardizing all building geometries to
  MultiPolygon before load fixed this.

## Future Improvements

- Add a lightweight automated test suite (e.g. pytest) around the
  cleaning functions
- Expand to a third dataset (e.g. schools or hospitals) for a richer
  POI-to-infrastructure proximity analysis
- Add a simple road-network-distance calculation (via `pgRouting`) as
  an alternative to straight-line proximity
- Parameterize the bounding box so the pipeline can be pointed at other
  Nigerian cities with minimal code changes
- Add incremental/scheduled re-ingestion to pick up OSM updates over time

## Skills Demonstrated

- Raw data acquisition from a live external API (Overpass/OSMnx),
  including handling real-world API constraints (query size limits,
  timeouts)
- Data validation and profiling before making changes to source data
- Geospatial data cleaning: invalid geometry repair, geometry type
  standardization, CRS reprojection, multi-value field normalization
- Relational + spatial database design (schema separation, appropriate
  data types, spatial indexing)
- SQL/PostGIS-based analytical transformation using real spatial
  functions matched to the actual analytical question
- Automated, code-generated data quality reporting
- Environment reproducibility via Docker and `.env`-based configuration
- Practical debugging of infrastructure, networking, and data-format
  issues under real constraints (a single laptop, no cloud services)

---

*Built as part of a Data Engineering / Geospatial AI portfolio, following
prior projects in Nigerian road accident risk analysis, satellite-based
urban growth analysis, and Lagos flood-risk prediction. This project
represents the transition from GIS/remote sensing analysis toward the
data infrastructure layer that supports it.*