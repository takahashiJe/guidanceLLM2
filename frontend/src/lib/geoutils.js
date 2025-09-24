// frontend/src/lib/geoutils.js

/**
 * @fileoverview 緯度経度に関する計算を行うユーティリティモジュール
 */

/**
 * 2つの緯度経度座標間の距離をメートル単位で計算します。
 * 計算にはHaversine（ハーバーサイン）公式を使用します。
 * @param {object} pos1 - 地点1の座標 { lat: number, lng: number }
 * @param {object} pos2 - 地点2の座標 { lat: number, lng: number }
 * @returns {number} 2点間の距離 (メートル)
 */
export function calculateDistance(pos1, pos2) {
  if (!pos1 || !pos2) return Infinity;

  const R = 6371e3; // 地球の半径 (メートル)
  const phi1 = pos1.lat * Math.PI / 180; // φ, λ in radians
  const phi2 = pos2.lat * Math.PI / 180;
  const deltaPhi = (pos2.lat - pos1.lat) * Math.PI / 180;
  const deltaLambda = (pos2.lng - pos1.lng) * Math.PI / 180;

  const a = Math.sin(deltaPhi / 2) * Math.sin(deltaPhi / 2) +
            Math.cos(phi1) * Math.cos(phi2) *
            Math.sin(deltaLambda / 2) * Math.sin(deltaLambda / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

  const d = R * c; // in metres
  return d;
}

/**
 * ユーザーの現在地が、指定されたルート上のどの移動モード（'car' or 'foot'）
 * の区間に最も近いかを判定します。
 * @param {object} currentPos - ユーザーの現在地座標 { lat: number, lng: number }
 * @param {Array} routeSegments - GeoJSON形式のルートセグメントの配列
 * 各セグメントは { mode: 'car'|'foot', geometry: { coordinates: [[lng, lat], ...] } }
 * @returns {string} 最も近い区間の移動モード ('car' または 'foot')。ルート情報がない場合は'car'をデフォルトとします。
 */
export function getCurrentTravelMode(currentPos, routeSegments) {
  // ルートセグメントのデータがない、または空配列の場合はデフォルトの'car'を返す
  if (!routeSegments || routeSegments.length === 0) {
    return 'car';
  }

  let closestMode = 'car'; // デフォルトの移動モード
  let minDistance = Infinity;

  // 全てのルートセグメント（'car', 'foot'）を反復処理
  for (const segment of routeSegments) {
    // セグメント内の全ての座標点を反復処理
    for (const coord of segment.geometry.coordinates) {
      const pointPos = { lat: coord[1], lng: coord[0] };
      const distance = calculateDistance(currentPos, pointPos);

      // これまでに見つかった最小距離よりも近ければ、情報を更新
      if (distance < minDistance) {
        minDistance = distance;
        closestMode = segment.mode;
      }
    }
  }

  return closestMode;
}