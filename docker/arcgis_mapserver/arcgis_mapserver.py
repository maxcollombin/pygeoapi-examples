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

        # Load collection from config
        self._load_collection_from_config(provider_def)

        LOGGER.debug(f"ArcGISMapServer initialized for layer {self.layer}")
        LOGGER.debug(f"Extent bbox: {self.extent_bbox}")
        LOGGER.debug(f"Extent CRS: {self.extent_crs}, EPSG={self.default_epsg}")

    def _load_collection_from_config(self, provider_def):
        """
        Load collection extents from local.config.yml based on provider name.
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
                        # Always treat CRS as string for downstream usage
                        self.extent_crs = str(crs_value) if crs_value is not None else None

                        if self.extent_crs:
                            match = re.search(r'(\d{4,5})$', self.extent_crs)
                            if match:
                                self.default_epsg = match.group(1)
                        else:
                            self.default_epsg = '4326'
                        return
            LOGGER.warning("No matching collection found in local.config.yml for this provider")

        except Exception as e:
            LOGGER.error(f"Could not load collection from config: {e}")

    def _apply_geometry_transform(self, feature, transform_fn):
        """
        Apply a geometry transformation function to a feature's geometry.
        """
        geom = feature.get('geometry')
        if geom:
            feature['geometry'] = transform_fn(geom)
        return feature

    def _custom_convert(self, item, transform_fn=None):
        """
        Convert ESRI JSON to GeoJSON feature with geometry transformation.
        """
        feature = convert(item, idAttribute=self.id_field)

        # Apply id_field logic
        if 'id' not in feature or feature['id'] is None:
            attrs = feature.get('properties', {})
            feature['id'] = (
                item.get(self.id_field)
                or attrs.get(self.id_field)
                or str(uuid.uuid4())
            )

        # Apply geometry transformation
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
        if not bbox or not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            raise ProviderQueryError("Invalid or missing bbox in collection extents.spatial.bbox")

        bbox = [float(x) for x in bbox]
        sr = self.default_epsg if self.default_epsg else "2056"
        geometry = ','.join(str(c) for c in bbox)
        tolerance = self.params.get('tolerance', 0)

        url = (
            f"{self.data}"
            f"?geometryType=esriGeometryEnvelope"
            f"&sr={sr}"
            f"&geometry={geometry}"
            f"&tolerance={tolerance}"
            f"&layers=all:{self.layer}"
            f"&f=json"
            f"&offset={offset or startindex}"
            f"&limit={limit}"
        )

        LOGGER.debug(f"MapServer query URL: {url}")

        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            features = []
            for item in data.get('results', []):
                feature = self._custom_convert(item, transform_fn=transform_fn)
                if feature.get('geometry') is not None:
                    features.append(feature)

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

    def get_item(self, item_id, transform_fn=None):
        """
        Fetch a single feature by item_id using the id_field logic.
        """
        if not self.collection:
            raise ProviderQueryError("No collection found in config or set manually.")

        # Build the item-specific URL
        url = f"{self.data}/{item_id}"
        LOGGER.debug(f"MapServer item URL: {url}")

        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            item = resp.json()
            feature = self._custom_convert(item, transform_fn=transform_fn)
            if feature.get('geometry') is None:
                raise ProviderQueryError(f"No geometry found for item {item_id}")
            return feature
        except requests.RequestException as err:
            raise ProviderQueryError(f"Connection error: {err}")
        except Exception as err:
            raise ProviderQueryError(f"Error querying MapServer API for item {item_id}: {err}")
