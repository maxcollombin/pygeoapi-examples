import logging
import re
import requests
import yaml
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import orient
from pygeoapi.provider.base import BaseProvider, ProviderQueryError

LOGGER = logging.getLogger(__name__)

class ArcGISMapServer(BaseProvider):
    """
    Provider for ArcGIS MapServer REST API, auto-loading its collection from config.
    """

    def __init__(self, provider_def):
        super().__init__(provider_def)
        self.layer = provider_def.get('layer')
        self.id_field = provider_def.get('id_field')
        self.params = provider_def.get('params', {})
        self.data = provider_def.get('data')
        self.extent_bbox = None
        self.extent_crs = None
        self.default_epsg = None
        self.collection = None

        # Load collection from config
        self._load_collection_from_config(provider_def)

        LOGGER.debug(f"ArcGISMapServer initialized for layer {self.layer}")
        LOGGER.debug(f"Extent bbox: {self.extent_bbox}")
        LOGGER.debug(f"Extent CRS: {self.extent_crs}, EPSG={self.default_epsg}")

    # Load collection details from config
    def _load_collection_from_config(self, provider_def):
        """
        Load collection details from local.config.yml based on provider name.
        """
        try:
            with open('/pygeoapi/local.config.yml', 'r') as f:
                config = yaml.safe_load(f)

            for name, res in config.get('resources', {}).items():
                providers = res.get('providers', [])
                for p in providers:
                    if p.get('name') == provider_def.get('name'):
                        self.collection = res
                        spatial = res.get('extents', {}).get('spatial', {})
                        self.extent_bbox = spatial.get('bbox')
                        crs_value = spatial.get('crs')
                        self.extent_crs = str(crs_value) if crs_value is not None else None

                        # Parse EPSG
                        if self.extent_crs:
                            match = re.search(r'(\d{4,5})$', self.extent_crs)
                            if match:
                                self.default_epsg = int(match.group(1))
                        else:
                            self.default_epsg = 4326
                        return
            LOGGER.warning("No matching collection found in local.config.yml for this provider")

        except Exception as e:
            LOGGER.error(f"Could not load collection from config: {e}")

    # Query method
    def query(self, startindex=0, limit=10, offset=None, **kwargs):
        """
        Query features from ArcGIS MapServer using the collection bbox.
        """
        if not self.collection:
            raise ProviderQueryError("No collection found in config or set manually.")

        # Get bbox from collection extents
        bbox = self.extent_bbox
        if not bbox or not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            raise ProviderQueryError("Invalid or missing bbox in collection extents.spatial.bbox")

        bbox = [float(x) for x in bbox]
        sr = self.default_epsg if self.default_epsg else 4326
        geometry = ','.join(str(c) for c in bbox)
        tolerance = self.params.get('tolerance', 0)

        url = (
            f"{self.data}"
            f"?geometryType=esriGeometryEnvelope"
            f"&sr={sr}"
            f"&geometry={geometry}"
            f"&tolerance={tolerance}"
            f"&layers=all:{self.layer}"
            f"&f=geojson"
            f"&limit={limit}"
            f"&offset={offset or startindex}"
        )

        LOGGER.debug(f"MapServer query URL: {url}")

        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            features = self._transform_geojson(data)

            return {
                'type': 'FeatureCollection',
                'features': features,
                'numberMatched': len(features),
                'numberReturned': len(features),
            }

        except requests.RequestException as err:
            raise ProviderQueryError(f"Connection error: {err}")
        except Exception as err:
            raise ProviderQueryError(f"Error querying MapServer API: {err}")

    # Geometry helpers
    def _esri_rings_to_geojson(self, rings):
        if not rings:
            return None
        polys = [
            orient(Polygon(r), sign=1.0)
            for r in rings
            if Polygon(r).is_valid and not Polygon(r).is_empty
        ]
        if not polys:
            return None
        if len(polys) == 1:
            return polys[0].__geo_interface__
        else:
            mp = MultiPolygon(polys)
            return orient(mp, sign=1.0).__geo_interface__

    def _transform_geojson(self, data):
        features = []
        if 'results' not in data:
            LOGGER.warning("No 'results' found in MapServer response")
            return features

        for item in data.get('results', []):
            geom = item.get('geometry')
            attrs = item.get('attributes', {})
            if not geom:
                continue

            # Correct polygon/multipolygon geometries
            if 'rings' in geom:
                geometry = self._esri_rings_to_geojson(geom.get('rings'))
            # Correct point geometries
            elif 'x' in geom and 'y' in geom:
                geometry = {
                    "type": "Point",
                    "coordinates": [geom['x'], geom['y']]
                }
            else:
                geometry = None

            feature_id = (
                item.get(self.id_field)
                or attrs.get(self.id_field)
                or item.get('featureId')
            )

            if geometry:
                features.append({
                    "type": "Feature",
                    "id": feature_id,
                    "geometry": geometry,
                    "properties": attrs
                })

        return features
