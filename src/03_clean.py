"""
03_clean.py

Cleans and standardizes the raw OSM data:
- Flattens any multi-value OSM tag columns (e.g. a road segment tagged
  with multiple highway values) down to a single value. These can show
  up as real Python lists, NumPy arrays (GeoPandas converts JSON array
  fields to ndarray on read), or - after a round trip through GeoJSON -
  as strings that merely look like lists (e.g. "['residential']"). We
  handle all three cases, so we never end up with that bracket-string
  format in the cleaned output.
- Reprojects to a projected CRS (EPSG:32632, UTM Zone 32N) for accurate
  length/area calculations. Raw data is in EPSG:4326 (degrees), which is
  not suitable for measuring distance or area.
- Standardizes geometry types (buildings must be Polygon/MultiPolygon;
  drops the small number of Point-only building records).
- Fixes any invalid geometries with Shapely's make_valid, even though
  validation found none - this keeps the pipeline robust if the raw
  data changes on a future run.
- Normalizes all building geometries to MultiPolygon. make_valid() can
  turn a slightly invalid Polygon into a MultiPolygon when it fixes a
  self-intersection, which would otherwise leave us with a mixed-type
  column that PostGIS rejects on load.
- Drops duplicate rows.
- Keeps only a small, useful set of columns instead of every sparse OSM tag.
- Calculates derived fields: road length (m), building area (sq m).

Prints record counts BEFORE and AFTER cleaning for the data quality report.
"""

import ast
import numpy as np
import geopandas as gpd
from pathlib import Path
from shapely.validation import make_valid
from shapely.geometry import MultiPolygon

RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
TARGET_CRS = "EPSG:32632"  # UTM Zone 32N - correct metric CRS for Abuja


def flatten_list_cell(val):
    """Some OSM columns can contain multiple tag values for a single
    feature (e.g. a road segment tagged with two highway values). These
    can appear as real Python lists, NumPy arrays (GeoPandas converts
    JSON array fields to ndarray on read), or - after an earlier round
    trip through GeoJSON - as strings that merely look like lists
    (e.g. "['residential']"). We handle all three cases and keep just
    the first value."""
    if isinstance(val, np.ndarray):
        return val[0] if val.size > 0 else None
    if isinstance(val, list):
        return val[0] if val else None
    if isinstance(val, str) and val.startswith("[") and val.endswith("]"):
        try:
            parsed = ast.literal_eval(val)
            if isinstance(parsed, list):
                return parsed[0] if parsed else None
        except (ValueError, SyntaxError):
            pass
    return val


def clean_roads():
    print("\n--- Cleaning roads ---")
    gdf = gpd.read_file(RAW_DIR / "raw_roads.geojson")
    before = len(gdf)

    non_geom_cols = [c for c in gdf.columns if c != "geometry"]
    for col in non_geom_cols:
        gdf[col] = gdf[col].apply(flatten_list_cell)

    gdf = gdf.drop(columns="geometry").astype(str).join(gdf["geometry"])
    gdf = gpd.GeoDataFrame(gdf, geometry="geometry", crs="EPSG:4326")
    gdf = gdf.drop_duplicates(subset=[c for c in gdf.columns if c != "geometry"])

    gdf = gdf[gdf.geometry.notna()]
    gdf["geometry"] = gdf["geometry"].apply(
        lambda g: g if g.is_valid else make_valid(g)
    )

    gdf = gdf.to_crs(TARGET_CRS)
    gdf["length_m"] = gdf.geometry.length

    keep_cols = ["osmid", "highway", "name", "oneway", "length_m", "geometry"]
    keep_cols = [c for c in keep_cols if c in gdf.columns]
    gdf = gdf[keep_cols]

    gdf["highway"] = gdf["highway"].astype(str).str.strip().str.lower()

    after = len(gdf)
    print(f"Records before cleaning: {before}")
    print(f"Records after cleaning:  {after}")

    out_path = PROCESSED_DIR / "cleaned_roads.geojson"
    gdf.to_file(out_path, driver="GeoJSON")
    print(f"Saved cleaned roads to {out_path}")
    return before, after


def clean_buildings():
    print("\n--- Cleaning buildings ---")
    gdf = gpd.read_file(RAW_DIR / "raw_buildings.geojson")
    before = len(gdf)

    non_geom_cols = [c for c in gdf.columns if c != "geometry"]
    for col in non_geom_cols:
        gdf[col] = gdf[col].apply(flatten_list_cell)

    gdf = gdf.drop(columns="geometry").astype(str).join(gdf["geometry"])
    gdf = gpd.GeoDataFrame(gdf, geometry="geometry", crs="EPSG:4326")
    gdf = gdf.drop_duplicates(subset=[c for c in gdf.columns if c != "geometry"])

    gdf = gdf[gdf.geometry.notna()]

    # Building footprints must be polygons - drop Point-only records,
    # they have no shape to measure area from
    gdf = gdf[gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]

    gdf["geometry"] = gdf["geometry"].apply(
        lambda g: g if g.is_valid else make_valid(g)
    )

    # Standardize all geometries to MultiPolygon - make_valid() can turn a
    # Polygon into a MultiPolygon when fixing self-intersections, so we
    # normalize everything to one consistent type before loading to PostGIS.
    gdf["geometry"] = gdf["geometry"].apply(
        lambda g: g if isinstance(g, MultiPolygon) else MultiPolygon([g])
    )

    gdf = gdf.to_crs(TARGET_CRS)
    gdf["area_sqm"] = gdf.geometry.area

    keep_cols = ["osmid", "building", "name", "area_sqm", "geometry"]
    keep_cols = [c for c in keep_cols if c in gdf.columns]
    gdf = gdf[keep_cols]

    gdf["building"] = gdf["building"].astype(str).str.strip().str.lower()

    after = len(gdf)
    print(f"Records before cleaning: {before}")
    print(f"Records after cleaning:  {after}")

    out_path = PROCESSED_DIR / "cleaned_buildings.geojson"
    gdf.to_file(out_path, driver="GeoJSON")
    print(f"Saved cleaned buildings to {out_path}")
    return before, after


if __name__ == "__main__":
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    clean_roads()
    clean_buildings()
    print("\nCleaning complete.")