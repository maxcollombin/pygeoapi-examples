import logging
import re
import requests
import yaml
import uuid
from pygeoapi.provider.base import BaseProvider, ProviderQueryError
from arcgis2geojson import convert

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
        self._load_collection_from_config(provider_def)

    def _load_collection_from_config(self, provider_def):
        """
        Load collection extents from local.config.yml based on provider name.
        """
        try:
            with open('/pygeoapi/local.config.yml', 'r') as f:
                config = yaml.safe_load(f)
            for name, res in config.get('resources', {}).items():
                for p in res.get('providers', []):
                    if p.get('name') == provider_def.get('name'):
                        self.collection = res
                        spatial = res.get('extents', {}).get('spatial', {})
                        self.extent_bbox = spatial.get('bbox')
                        self.extent_crs = str(spatial.get('crs')) if spatial.get('crs') is not None else None
                        self.default_epsg = re.search(r'(\d{4,5})$', self.extent_crs).group(1) if self.extent_crs and re.search(r'(\d{4,5})$', self.extent_crs) else '4326'
                        return
            LOGGER.warning("No matching collection found in local.config.yml for this provider")
        except Exception as e:
            LOGGER.error(f"Could not load collection from config: {e}")

    def _apply_geometry_transform(self, feature, transform_fn):
        """
        Apply a geometry transformation function to a feature's geometry.
        """
        if feature.get('geometry'):
            feature['geometry'] = transform_fn(feature['geometry'])
        return feature

    def _custom_convert(self, item, transform_fn=None):
        """
        Convert ESRI JSON to GeoJSON feature with geometry transformation.
        """
        feature = convert(item, idAttribute=self.id_field)
        feature['type'] = 'Feature'
        attrs = feature.get('properties', {})
        feature['id'] = item.get(self.id_field) or attrs.get(self.id_field) or str(uuid.uuid4())
        if transform_fn and feature.get('geometry'):
            feature = self._apply_geometry_transform(feature, transform_fn)
        return feature

    def query(self, startindex=0, limit=10, offset=None, transform_fn=None, **kwargs):
        """
        Query features from the ArcGIS MapServer REST API.
        """
        if not self.collection:
            raise ProviderQueryError("No collection found in config or set manually.")
        bbox = self.extent_bbox
        if not (isinstance(bbox, (list, tuple)) and len(bbox) == 4):
            raise ProviderQueryError("Invalid or missing bbox in collection extents.spatial.bbox")
        bbox = [float(x) for x in bbox]
        sr = self.default_epsg or "2056"
        geometry = ','.join(map(str, bbox))
        tolerance = self.params.get('tolerance', 0)
        url = (
            f"{self.data}/identify?geometryType=esriGeometryEnvelope&sr={sr}"
            f"&geometry={geometry}&tolerance={tolerance}&layers=all:{self.layer}"
            f"&f=json&offset={offset or startindex}&limit={limit}"
        )
        LOGGER.debug(f"MapServer query URL: {url}")
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            features = [self._custom_convert(item, transform_fn=transform_fn)
                        for item in data.get('results', [])
                        if self._custom_convert(item, transform_fn=transform_fn).get('geometry') is not None]
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

    def get_item(self, item_id, transform_fn=None, **kwargs):
        """
        Fetch a single item by its ID from the ArcGIS MapServer REST API.
        """
        if not self.collection:
            raise ProviderQueryError("No collection found in config or set manually.")
        base_url = f"{self.data}/{self.layer}/{item_id}"
        sr_value = self.extent_crs or self.default_epsg or "4326"
        params = {"geometryFormat": "geojson", "sr": sr_value}
        params.update(kwargs.get("query_params", {}))
        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{base_url}?{query_string}" if query_string else base_url
        LOGGER.debug(f"MapServer getItem URL: {url}")
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            item = resp.json()
            LOGGER.debug(f"Raw item response: {item}")
            feature = self._custom_convert(item, transform_fn=transform_fn)
            # Set id from id_field if present, else fallback to item_id
            feature_id = (
                item.get(self.id_field)
                or item.get('feature', {}).get(self.id_field)
                or feature.get('properties', {}).get(self.id_field)
            )
            feature['id'] = feature_id if feature_id is not None else str(item_id)
            # Geometry handling
            if not feature.get('geometry'):
                esri_geom = item.get('feature', {}).get('geometry', {})
                if 'x' in esri_geom and 'y' in esri_geom:
                    feature['geometry'] = {"type": "Point", "coordinates": [esri_geom['x'], esri_geom['y']]}
                else:
                    geometry = item.get('geometry') or esri_geom
                    if geometry and isinstance(geometry, dict) and geometry.get('type') and geometry.get('coordinates'):
                        feature['geometry'] = geometry
                        if transform_fn:
                            feature = self._apply_geometry_transform(feature, transform_fn)
                    else:
                        raise ProviderQueryError(f"No valid geometry found for item {item_id}. Raw response: {item}")
            feature['type'] = 'Feature'
            geom = feature.get('geometry')
            if geom and geom.get('type') == 'MultiPolygon' and len(geom.get('coordinates', [])) == 1:
                feature['geometry'] = {'type': 'Polygon', 'coordinates': geom['coordinates'][0]}
            # Properties handling
            properties = item.get('feature', {}).get('properties') or item.get('properties') or {}
            feature['properties'] = properties if isinstance(properties, dict) else {}
            return feature
        except requests.RequestException as err:
            raise ProviderQueryError(f"Connection error: {err}")
        except Exception as err:
            raise ProviderQueryError(f"Error querying MapServer API for item {item_id}: {err}")

    def get(self, identifier, transform_fn=None, **kwargs):
        """
        Fetch a single item by its ID from the ArcGIS MapServer REST API.
        """
        return self.get_item(identifier, transform_fn=transform_fn, **kwargs)