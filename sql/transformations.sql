-- transformations.sql
-- Builds analytics-ready tables from the staging layer using PostGIS.
--
-- Three tables:
--   analytics.road_summary        - road stats grouped by road type (highway tag)
--   analytics.building_summary    - building stats grouped by building type
--   analytics.building_road_proximity - for each building, its distance
--                                        to the nearest road, and whether
--                                        it's within 50m of one
--
-- These exist to prove the cleaned staging data is actually usable for
-- real infrastructure questions, not just sitting in a database.

DROP TABLE IF EXISTS analytics.road_summary;
CREATE TABLE analytics.road_summary AS
SELECT
    highway AS road_type,
    COUNT(*) AS segment_count,
    ROUND(SUM(length_m)::numeric, 2) AS total_length_m,
    ROUND(AVG(length_m)::numeric, 2) AS avg_length_m
FROM staging.cleaned_roads
GROUP BY highway
ORDER BY total_length_m DESC;

DROP TABLE IF EXISTS analytics.building_summary;
CREATE TABLE analytics.building_summary AS
SELECT
    building AS building_type,
    COUNT(*) AS building_count,
    ROUND(SUM(area_sqm)::numeric, 2) AS total_area_sqm,
    ROUND(AVG(area_sqm)::numeric, 2) AS avg_area_sqm
FROM staging.cleaned_buildings
GROUP BY building
ORDER BY building_count DESC;

-- For each building, find distance to the nearest road using ST_DWithin
-- (fast, index-assisted search within 200m) combined with an exact
-- nearest-neighbour distance calculation. This demonstrates a genuine
-- spatial join, not just an attribute-based one.
DROP TABLE IF EXISTS analytics.building_road_proximity;
CREATE TABLE analytics.building_road_proximity AS
SELECT
    b.id AS building_id,
    b.building AS building_type,
    b.area_sqm,
    MIN(ST_Distance(b.geom, r.geom)) AS distance_to_nearest_road_m,
    BOOL_OR(ST_DWithin(b.geom, r.geom, 50)) AS within_50m_of_road
FROM staging.cleaned_buildings b
JOIN staging.cleaned_roads r
    ON ST_DWithin(b.geom, r.geom, 200)
GROUP BY b.id, b.building, b.area_sqm;

CREATE INDEX idx_building_road_proximity_building_id
    ON analytics.building_road_proximity (building_id);