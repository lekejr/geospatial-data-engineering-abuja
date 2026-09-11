"""
02_validate.py

Inspects the raw OSM data BEFORE any cleaning happens. Produces an honest
snapshot of data quality issues: missing/invalid geometries, duplicates,
CRS, and geometry type distribution.

This does not fix anything - it only reports. Fixing happens in 03_clean.py.
The counts printed here become the "before cleaning" baseline for the
final data_quality_report.csv.
"""

import geopandas as gpd
from pathlib import Path

RAW_DIR = Path("data/raw")


def inspect(gdf: gpd.GeoDataFrame, name: str) -> dict:
    print(f"\n--- {name} ---")

    total_records = len(gdf)
    null_geom = gdf.geometry.isna().sum()
    invalid_geom = (~gdf.geometry.is_valid).sum()

    # Some OSM columns (e.g. osmid, name, highway) can contain lists when a
    # feature has multiple tag values. Lists aren't hashable, so we convert
    # every non-geometry column to string just for the duplicate check.
    non_geom = gdf.drop(columns="geometry").astype(str)
    duplicate_rows = non_geom.duplicated().sum()

    geom_types = gdf.geometry.geom_type.value_counts().to_dict()
    crs = gdf.crs

    print(f"Total records:       {total_records}")
    print(f"Null geometries:     {null_geom}")
    print(f"Invalid geometries:  {invalid_geom}")
    print(f"Duplicate rows:      {duplicate_rows}")
    print(f"Geometry types:      {geom_types}")
    print(f"CRS:                 {crs}")

    return {
        "dataset": name,
        "total_records": total_records,
        "null_geometries": null_geom,
        "invalid_geometries": invalid_geom,
        "duplicate_rows": duplicate_rows,
        "geometry_types": geom_types,
        "crs": str(crs),
    }


if __name__ == "__main__":
    roads = gpd.read_file(RAW_DIR / "raw_roads.geojson")
    buildings = gpd.read_file(RAW_DIR / "raw_buildings.geojson")

    inspect(roads, "raw_roads")
    inspect(buildings, "raw_buildings")