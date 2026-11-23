from io import BytesIO
from urllib.request import urlopen
import geopandas as gpd

COUNTIES_ZIP_URL = "https://www.weather.gov/source/gis/Shapefiles/County/c_16ap26.zip"
ZONES_ZIP_URL = "https://www.weather.gov/source/gis/Shapefiles/WSOM/z_16ap26.zip"


def download_zip_buffer(url):
    with urlopen(url) as response:
        return BytesIO(response.read())


def transform_geospatial_counties(input_file, output_file):
    gdf = gpd.read_file(input_file)

    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    centroids = gdf.geometry.centroid
    out = gdf.drop(columns="geometry").copy()
    out["LONGITUDE"] = centroids.x
    out["LATITUDE"] = centroids.y
    out = out.drop(columns=["FE_AREA", "LON", "LAT", "CWA"], errors="ignore")

    fips_5 = out["FIPS"].astype(str).str.strip().str.zfill(5)

    formatted = out.assign(
        state_abbr=out["STATE"].astype(str).str.strip().str.upper(),
        state_fips=fips_5.str[:2],
        county_name=out["COUNTYNAME"],
        county_fips=fips_5.str[2:],
        latitude=out["LATITUDE"],
        longitude=out["LONGITUDE"],
    )[
        [
            "state_abbr",
            "state_fips",
            "county_name",
            "county_fips",
            "latitude",
            "longitude",
        ]
    ]

    formatted.to_csv(output_file, index=False)
    return formatted


def build_state_fips_map(counties_df):
    pairs = counties_df[["state_abbr", "state_fips"]].dropna().drop_duplicates()
    return dict(
        zip(
            pairs["state_abbr"].astype(str).str.strip().str.upper(),
            pairs["state_fips"].astype(str).str.strip().str.zfill(2),
        )
    )


def transform_geospatial_zones(input_file, output_file, state_fips_map=None):
    gdf = gpd.read_file(input_file)

    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    centroids = gdf.geometry.centroid
    out = gdf.drop(columns="geometry").copy()
    out["LONGITUDE"] = centroids.x
    out["LATITUDE"] = centroids.y

    state_col = out["STATE"] if "STATE" in out.columns else out["STATE_ABBRV"]
    clean_abbrv = state_col.astype(str).str.strip().str.upper()
    fips_lookup = state_fips_map or {}

    formatted = out.assign(
        state_abbrv=clean_abbrv,
        state_fips=clean_abbrv.map(fips_lookup),
        zone_name=out["NAME"],
        zone_fips=out["ZONE"].astype(str).str.strip().str.zfill(3),
        longitude=out["LONGITUDE"],
        latitude=out["LATITUDE"],
    )[
        [
            "state_abbrv",
            "state_fips",
            "zone_name",
            "zone_fips",
            "longitude",
            "latitude",
        ]
    ]

    formatted.to_csv(output_file, index=False)
    return formatted


if __name__ == "__main__":
    counties_buf = download_zip_buffer(COUNTIES_ZIP_URL)
    zones_buf = download_zip_buffer(ZONES_ZIP_URL)

    counties_df = transform_geospatial_counties(
        input_file=counties_buf,
        output_file="master-dataset/dim_counties.csv",
    )

    state_fips_map = build_state_fips_map(counties_df)

    zones_df = transform_geospatial_zones(
        input_file=zones_buf,
        output_file="master-dataset/dim_zones.csv",
        state_fips_map=state_fips_map,
    )