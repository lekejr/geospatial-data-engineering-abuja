-- schema.sql
-- Defines the database structure for the Abuja geospatial pipeline.
--
-- Two schemas are used:
--   staging   - cleaned data loaded directly from Python (source of truth
--               for anything downstream)
--   analytics - derived, query-ready tables built with SQL from staging
--
-- We skip a separate "raw" schema in the database itself, since the raw
-- files already live untouched in data/raw/ on disk. Loading raw OSM data
-- into Postgres unchanged would just duplicate that without adding value -
-- the staging schema is the first point where the database actually holds
-- meaningful, validated data.

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS analytics;

-- staging.cleaned_roads
-- Holds cleaned road segments with derived length. This is the base table
-- all road analytics are built from.
DROP TABLE IF EXISTS staging.cleaned_roads;
CREATE TABLE staging.cleaned_roads (
    id SERIAL PRIMARY KEY,
    osmid TEXT,
    highway TEXT,
    name TEXT,
    oneway TEXT,
    length_m DOUBLE PRECISION,
    geom GEOMETRY(LINESTRING, 32632)
);

CREATE INDEX idx_cleaned_roads_geom ON staging.cleaned_roads USING GIST (geom);

-- staging.cleaned_buildings
-- Holds cleaned building footprints with derived area. Base table for
-- all building analytics.
DROP TABLE IF EXISTS staging.cleaned_buildings;
CREATE TABLE staging.cleaned_buildings (
    id SERIAL PRIMARY KEY,
    osmid TEXT,
    building TEXT,
    name TEXT,
    area_sqm DOUBLE PRECISION,
    geom GEOMETRY(MULTIPOLYGON, 32632)
);

CREATE INDEX idx_cleaned_buildings_geom ON staging.cleaned_buildings USING GIST (geom);