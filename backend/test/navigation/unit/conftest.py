# absolute imports 前提で、プロジェクトルートを sys.path に通す
import sys
from pathlib import Path
import math
import pytest

# このファイルは backend/test/navigation/unit/ 配下にある想定
ROOT = Path(__file__).resolve().parents[4]  # → プロジェクトルート
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def sample_waypoints():
    # (lat, lon) 順。routing 側で lon,lat に並べ替える前提
    # current → A → B → C → current
    return [
        (39.2000, 139.9000),  # current
        (39.3000, 139.9500),  # A
        (39.3500, 139.9800),  # B
        (39.2500, 139.9600),  # C
        (39.2000, 139.9000),  # back to current
    ]


@pytest.fixture
def simple_polyline():
    # lon,lat の折れ線（OSRM準拠）
    return [
        [139.9000, 39.2000],
        [139.9250, 39.2250],
        [139.9500, 39.2500],
        [139.9750, 39.2750],
    ]


@pytest.fixture
def simple_segments():
    # polyline のインデックス範囲をレッグに対応付ける
    return [
        {"mode": "car", "start_idx": 0, "end_idx": 1},
        {"mode": "foot", "start_idx": 1, "end_idx": 3},
    ]


@pytest.fixture
def poi_hits_near_first_leg():
    # reduce_hits_to_along_pois に与えるフェイクヒット
    # 形式は reducer 実装に依存しないように最小フィールドだけ用意
    return [
        {"spot_id": "D", "name": "Spot D", "lon": 139.9100, "lat": 39.2100},
        {"spot_id": "E", "name": "Spot E", "lon": 139.9150, "lat": 39.2150},
    ]


def approx_equal(a: float, b: float, rel=1e-2, abs_=1e-6):
    return math.isclose(a, b, rel_tol=rel, abs_tol=abs_)


@pytest.fixture
def approx():
    return approx_equal
