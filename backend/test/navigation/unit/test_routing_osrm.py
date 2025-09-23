import re
from backend.worker.app.services.routing.osrm_client import build_osrm_url

def test_build_osrm_url__orders_lonlat_and_params():
    src = (39.2000, 139.9000)  # lat, lon
    dst = (39.2500, 139.9600)  # lat, lon
    url = build_osrm_url("car", src, dst)

    # lon,lat;lon,lat の順になっていること
    assert "/route/v1/car/139.9,39.2;139.96,39.25" in url

    # 必須クエリが付与されていること
    assert "geometries=geojson" in url
    assert "overview=full" in url
    assert "steps=true" in url

    # 余計な二重 ? や ;; がないこと
    assert re.search(r"\?.+=.+", url) is not None
    assert ";;" not in url
