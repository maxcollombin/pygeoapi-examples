# Étendre l'image officielle de pygeoapi
FROM geopython/pygeoapi:latest

# Passer à l'environnement virtuel déjà utilisé par pygeoapi
ENV VIRTUAL_ENV=/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Installer le module Python supplémentaire
RUN pip install --no-cache-dir arcgis2geojson

# Copier ton provider custom
COPY arcgis_mapserver.py /pygeoapi/arcgis_mapserver.py
