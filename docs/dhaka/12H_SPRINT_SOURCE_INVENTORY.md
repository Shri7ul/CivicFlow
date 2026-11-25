# 12-Hour Sprint — Source Inventory

Scope: evidence discovery and verification only. No source in this inventory has been approved for operational use, pilot activation, or automated decisioning.

## Summary

| # | Source | Endpoint / portal probed | Result | Evidence status |
|---:|---|---|---|---|
| 1 | Bangladesh NSDI / SuperMap | `https://www.nsdi.gov.bd/`, `https://nsdi.gov.bd/` | HTTP 523 from this environment; web search found only an ArcGIS item and reseller pages, not a verifiable public NSDI feature service | **Blocked / unverified**. No NSDI geometry acquired. |
| 2 | Bangladesh GIS Portal (BGISP) | `https://gis.gov.bd/`, `/api/geocode-layers/`, `/api/admin-boundary-layers/`, `www.arcgisbd.com` ArcGIS services | HTTP 200. Public API exposed official layer catalog. City corporation layer 242 and union/ward layer 245 queried successfully in EPSG:4326 | **Acquired — strongest official boundary evidence**. License and data vintage not stated in public service metadata. |
| 3 | RAJUK | `https://rajuk.gov.bd/` | HTTP 200. Site content is notices, publications, e-services and document links. No public GIS download, feature service or REST endpoint identified on the homepage | **Blocked / no dataset identified**. |
| 4 | GeoDASH | `https://geodash.gov.bd/`, `https://www.geodash.gov.bd/` | DNS resolution failed (`Could not resolve host`) | **Blocked**. No data acquired. |
| 5 | Bangladesh Open Data | `https://data.gov.bd/` | HTTP 200; catalog groups exist. CKAN-style endpoints returned 404 or malformed responses, so no usable catalog API. No Dhaka geospatial dataset identified | **Blocked / no dataset identified**. |
| 6 | World Bank | `https://api.worldbank.org/v2/country/BD/indicator/SP.URB.TOTL?format=json&date=2015:2025&per_page=100` | HTTP 200. `lastupdated=2026-11-11`, 11 annual rows acquired | **Acquired — national context only**. Not Dhaka-specific and not ground truth. |
| 7 | ESA EO4SD | `https://www.eo4sd.eu/` | DNS resolution failed. HDX search found historical flood proxy maps such as `eos-rs-bangladesh-floods-aug-2023` | **Not acquired**. Event-specific historical products are not current operational evidence. |
| 8 | Bangladesh Flood Forecasting and Warning Centre | `https://www.ffwc.gov.bd/` | HTTP 200. No downloadable GIS feed or API identified from the site within this sprint | **No dataset identified**. HDX flood layers are third-party/historical, not an FFWC operational feed. |
| 9 | BMD | `https://www.bmd.gov.bd/` | HTTP 200. No BMD rainfall/meteorological download or API identified. HDX search for BMD rainfall returned zero matching datasets | **No dataset identified**. |
| 10 | DWASA | `https://www.dwasa.org.bd/` | TLS trust failure (`SEC_E_UNTRUSTED_ROOT`) and connection failure. HDX search for Dhaka drainage/WASA returned zero matching datasets | **Blocked**. No drainage or waterlogging evidence acquired. |
| 11 | BBS | `https://www.bbs.gov.bd/` | HTTP 200. HDX contains BBS-linked census and population packages (`cod-ps-bgd`, census tables, subnational boundaries) | **Discovered, not acquired**. License and relevance review required before acquisition. |
| 12 | Open geospatial sources | geoBoundaries API, HDX CKAN API, OpenStreetMap/Overpass | geoBoundaries ADM2/3/4 metadata and GeoJSON acquired; HDX COD-AB v03 acquired; existing bounded OSM research cell re-verified | **Acquired as research/context evidence**. Not authoritative DNCC/DSCC approval. |

## BGISP discovery detail

The BGISP homepage is a single-page React application. The public JavaScript bundle exposed these same-origin endpoints:

- `/api/geocode-layers/`
- `/api/admin-boundary-layers/`
- `/api/get_districts_geocode_filter/`
- `/api/get_citycorporations_geocode_filter/`
- `/api/data/download/`

The layer catalog returned official ArcGIS service URLs hosted at `https://www.arcgisbd.com/server/rest/services/BBS009/...`. The following were queried successfully:

| Layer | Service | Key result |
|---|---|---|
| City corporation | `.../geo_boundary_citycorporation/FeatureServer/242` | 12 features, including DNCC (`city_geo_code=302625`) and DSCC (`302620`); EPSG:4326; JSON/geoJSON/PBF supported |
| Union/ward | `.../geo_boundary_unionward/FeatureServer/245` | 254 features in Dhaka district; 76 DNCC + 88 DSCC wards; EPSG:4326 |

The public service metadata does **not** state a license, copyright text, data vintage, or last edit date. Those gaps remain blockers to formal approval.

## Sources deliberately not treated as evidence

- Nominatim DNCC office polygon — a point-of-interest footprint, not an administrative boundary.
- OpenStreetMap research cell — community-mapped infrastructure context only.
- Historical flood proxy maps — event-specific raster/vector products, not current CivicFlow incidents.
- National World Bank indicators — useful context, but not ward-level or Dhaka-level observations.
- CKAN/malformed portal responses — not represented as datasets.

## No fabrication

No synthetic boundary, incident, field observation, ground-truth label, or model prediction was created during this source investigation.
