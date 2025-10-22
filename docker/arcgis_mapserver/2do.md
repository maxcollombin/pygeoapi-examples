# TODO

Adapter le script en utilisant cette logique de construction de requête

https://api3.geo.admin.ch/rest/services/api/MapServer/identify?geometryType=esriGeometryEnvelope&sr=2056&geometry=2409364.994674947,900944.2778558197,2934601.5794937545,1355924.860958274&tolerance=0&layers=all:ch.swisstopo.swissboundaries3d-gemeinde-flaeche.fill&f=json


https://api3.geo.admin.ch/rest/services/api/MapServer/identify?geometryType=esriGeometryEnvelope&sr=2056
&geometry=2420000.0,1030000.0,2900000.0,1350000.0
&tolerance=0
&layers=all:ch.babs.notfalltreffpunkte
&limit=5
&f=geojson





https://api3.geo.admin.ch/rest/services/api/MapServer/all:ch.swisstopo.swissboundaries3d-gemeinde-flaeche.fill



https://api3.geo.admin.ch/rest/services/api/MapServer/all:ch.swisstopo.swissboundaries3d-gemeinde-flaeche.fill/11348-1850

Rechercher le bbox max pour les données geoadmin
les requêtes sont limitées à 200

2409364.994674947,900944.2778558197,2934601.5794937545,1355924.860958274

https://api3.geo.admin.ch/rest/services/api/MapServer/identify?
geometry=&geometryType=esriGeometryEnvelope
&layers=all:ch.swisstopo.swissboundaries3d-gemeinde-flaeche.fill
&sr=2056
&tolerance=0
&returnGeometry=true
&returnZ=false
&f=geojson
&resultOffset=0
&resultRecordCount=1


File "/pygeoapi/pygeoapi/provider/ogr.py", line 377, in query raise ProviderConnectionError(err)
pygeoapi.provider.base.ProviderConnectionError: Failed to read ESRIJSON data
May be caused by: Invalid FeatureCollection object. Missing 'features' member.

https://map.bgs.ac.uk/arcgis/rest/services/GeoIndex_Onshore/boreholes/MapServer/0/query?where=BGS_ID=BGS_ID&outfields=*&f=json

https://api3.geo.admin.ch/rest/services/api/MapServer/all:ch.swisstopo.swissboundaries3d-gemeinde-flaeche.fill/query?where=BGS_ID=BGS_ID&outfields=*&f=json

https://api3.geo.admin.ch/rest/services/api/MapServer/ch.swisstopo.swissboundaries3d-gemeinde-flaeche.fill/query?where=gde_nr=gde_nr&outfields=*&f=json
