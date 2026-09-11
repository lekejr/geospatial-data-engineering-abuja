"""
01_ingest.py

Pulls raw OpenStreetMap data for central Abuja (FCT, Nigeria) using a
bounding box covering the main urban districts (Wuse, Garki, Maitama,
Asokoro, Central Business District):
- Road network (drivable roads)
- Building footprints

This is the RAW ingestion step. No cleaning or transformation happens here.
The output is saved exactly as OSM returns it, so we always have an
untouched copy to fall back on.

NOTE: We use a bounding box rather than an administrative place name.
Some OSM administrative boundaries for Abuja's sub-districts are not
cleanly mapped as polygons, which caused geocoding queries to fail.
A bounding box gives predictable, reproducible results and lets us
directly control the size of the area being pulled.
"""

import osmnx as ox
from pathlib import Path

ox.settings.timeout = 300

# Bounding box covering central Abuja's main urban districts
# (west, south, east, north)
BBOX = (7.40, 9.00, 7.55, 9.12)

RAW_DIR = Path("data/raw")


def ingest_roads():
    print(f"Fetching road network for bbox: {BBOX}")
    graph = ox.graph_from_bbox(bbox=BBOX, network_type="drive")
    edges = ox.graph_to_gdfs(graph, nodes=False, edges=True)
    edges = edges.reset_index()
    out_path = RAW_DIR / "raw_roads.geojson"
    edges.to_file(out_path, driver="GeoJSON")
    print(f"Saved {len(edges)} road segments to {out_path}")
    return edges


def ingest_buildings():
    print(f"Fetching building footprints for bbox: {BBOX}")
    buildings = ox.features_from_bbox(bbox=BBOX, tags={"building": True})
    buildings = buildings.reset_index()
    out_path = RAW_DIR / "raw_buildings.geojson"
    buildings.to_file(out_path, driver="GeoJSON")
    print(f"Saved {len(buildings)} buildings to {out_path}")
    return buildings


if __name__ == "__main__":
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    ingest_roads()
    ingest_buildings()
    print("Ingestion complete.")