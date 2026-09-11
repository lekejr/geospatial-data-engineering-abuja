"""
04_load_postgis.py

Loads the cleaned GeoJSON files (data/processed/) into the PostgreSQL/PostGIS
staging tables defined in sql/schema.sql.

Uses SQLAlchemy + GeoPandas' to_postgis, which handles the geometry
conversion into PostGIS-native types automatically.

Credentials are read from .env - never hardcoded.
"""

import geopandas as gpd
from sqlalchemy import create_engine
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")

PROCESSED_DIR = Path("data/processed")


def get_engine():
    conn_str = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    return create_engine(conn_str)


def load_roads(engine):
    print("Loading roads into staging.cleaned_roads ...")
    gdf = gpd.read_file(PROCESSED_DIR / "cleaned_roads.geojson")
    gdf = gdf.rename(columns={"geometry": "geom"}).set_geometry("geom")
    gdf.to_postgis("cleaned_roads", engine, schema="staging", if_exists="append", index=False)
    print(f"Loaded {len(gdf)} road records.")
    return len(gdf)


def load_buildings(engine):
    print("Loading buildings into staging.cleaned_buildings ...")
    gdf = gpd.read_file(PROCESSED_DIR / "cleaned_buildings.geojson")
    gdf = gdf.rename(columns={"geometry": "geom"}).set_geometry("geom")
    gdf.to_postgis("cleaned_buildings", engine, schema="staging", if_exists="append", index=False)
    print(f"Loaded {len(gdf)} building records.")
    return len(gdf)


if __name__ == "__main__":
    engine = get_engine()
    roads_loaded = load_roads(engine)
    buildings_loaded = load_buildings(engine)
    print(f"\nLoad complete. Roads: {roads_loaded}, Buildings: {buildings_loaded}")