"""
05_quality_report.py

Generates outputs/data_quality_report.csv by querying the raw files,
the cleaned files, and the live PostGIS database directly. Every number
in this report is computed by code, not typed by hand.

This is the final proof-of-quality step in the pipeline: it shows records
before cleaning, after cleaning, and successfully loaded, alongside
structural checks (geometry validity, CRS, geometry types) on the raw data.
"""

import geopandas as gpd
import pandas as pd
from pathlib import Path
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

load_dotenv()

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")

RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
OUTPUT_DIR = Path("outputs")


def get_engine():
    conn_str = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    return create_engine(conn_str)


def profile_raw(path: Path, name: str) -> dict:
    gdf = gpd.read_file(path)
    return {
        "dataset": name,
        "raw_records": len(gdf),
        "raw_null_geometries": int(gdf.geometry.isna().sum()),
        "raw_invalid_geometries": int((~gdf.geometry.is_valid).sum()),
        "raw_geometry_types": ", ".join(
            f"{k}:{v}" for k, v in gdf.geometry.geom_type.value_counts().items()
        ),
        "raw_crs": str(gdf.crs),
    }


def profile_cleaned(path: Path) -> int:
    gdf = gpd.read_file(path)
    return len(gdf)


def profile_loaded(engine, schema: str, table: str) -> int:
    with engine.connect() as conn:
        result = conn.execute(text(f"SELECT COUNT(*) FROM {schema}.{table}"))
        return result.scalar()


if __name__ == "__main__":
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    engine = get_engine()

    rows = []

    roads_raw = profile_raw(RAW_DIR / "raw_roads.geojson", "roads")
    roads_raw["cleaned_records"] = profile_cleaned(PROCESSED_DIR / "cleaned_roads.geojson")
    roads_raw["loaded_records"] = profile_loaded(engine, "staging", "cleaned_roads")
    rows.append(roads_raw)

    buildings_raw = profile_raw(RAW_DIR / "raw_buildings.geojson", "buildings")
    buildings_raw["cleaned_records"] = profile_cleaned(PROCESSED_DIR / "cleaned_buildings.geojson")
    buildings_raw["loaded_records"] = profile_loaded(engine, "staging", "cleaned_buildings")
    rows.append(buildings_raw)

    report_df = pd.DataFrame(rows)

    col_order = [
        "dataset",
        "raw_records",
        "cleaned_records",
        "loaded_records",
        "raw_null_geometries",
        "raw_invalid_geometries",
        "raw_geometry_types",
        "raw_crs",
    ]
    report_df = report_df[col_order]

    out_path = OUTPUT_DIR / "data_quality_report.csv"
    report_df.to_csv(out_path, index=False)

    print("Data quality report generated:")
    print(report_df.to_string(index=False))
    print(f"\nSaved to {out_path}")