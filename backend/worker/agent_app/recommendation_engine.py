import pandas as pd
import json
import os
import pickle
import faiss
import numpy as np
from sklearn.preprocessing import OneHotEncoder

class RecommendationEngine:
    def __init__(self, data_dir='data/processed'):
        print("Initializing Recommendation Engine...")
        self.spot_info = self._load_json(os.path.join(data_dir, 'spot_info.json'))
        self.travel_matrix = self._load_json(os.path.join(data_dir, 'travel_matrix.json'))
        self.persona_recommendations = self._load_json(os.path.join(data_dir, 'persona_recommendations.json'))
        self.spot_id_map = self._load_json(os.path.join(data_dir, 'spot_id_map.json'))
        
        self.faiss_index = faiss.read_index(os.path.join(data_dir, 'spot_embeddings.faiss'))
        
        # モデルとエンコーダーを読み込む
        model_payload = self._load_pickle(os.path.join(data_dir, 'persona_model.pkl'))
        self.persona_model = model_payload['kmeans_model']
        self.encoder = model_payload['encoder']
        
        self.int_to_spot_id = {v: k for k, v in self.spot_id_map.items()}
        print("Recommendation Engine initialized successfully.")

    def _load_json(self, path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _load_pickle(self, path):
        with open(path, 'rb') as f:
            return pickle.load(f)

    def get_recommendations(self, user_profile, itinerary=None, positive_keywords=None, negative_keywords=None):
        if itinerary is None:
            itinerary = []

        # --- 1. ペルソナ分類 ---
        processed_profile = self._preprocess_profile(user_profile)
        persona_id = self.persona_model.predict(processed_profile)[0]
        print(f"User classified into persona: {persona_id}")

        scores = {}

        # --- 2. 候補生成 ---
        persona_recos = self.persona_recommendations.get(str(persona_id), [])
        for spot_id in persona_recos:
            scores.setdefault(spot_id, {'score': 0, 'reasons': []})
            scores[spot_id]['score'] += 1.0
            scores[spot_id]['reasons'].append('persona_match')

        if itinerary:
            last_spot = itinerary[-1]
            if last_spot in self.travel_matrix:
                nearby_spots = sorted(self.travel_matrix[last_spot].items(), key=lambda item: item[1]['minutes'])
                for spot_id, travel_info in nearby_spots[:5]:
                    scores.setdefault(spot_id, {'score': 0, 'reasons': []})
                    scores[spot_id]['score'] += 0.5
                    scores[spot_id]['reasons'].append('nearby')

        # --- 3. フィルタリング ---
        for spot_id in itinerary:
            if spot_id in scores:
                del scores[spot_id]

        # --- 4. ランキング ---
        sorted_spots = sorted(scores.items(), key=lambda item: item[1]['score'], reverse=True)

        # --- 5. 出力形式に変換 ---
        recommendations = []
        for spot_id, data in sorted_spots[:5]:
            recommendations.append({
                "spot_id": spot_id,
                "score": data['score'],
                "reason": list(set(data['reasons']))
            })
        
        return recommendations

    def _preprocess_profile(self, user_profile):
        # user_profile辞書から学習時と同じ特徴量を抽出してDataFrameを作成
        profile_df = pd.DataFrame([user_profile])
        features_order = ['Travel_Style', 'Travel_Frequency', 'Preferred_Destinations']
        profile_df = profile_df[features_order]
        
        # 保存したエンコーダーで変換
        return self.encoder.transform(profile_df)

# --- 実行例 ---
if __name__ == '__main__':
    engine = RecommendationEngine()

    # ケース1: 初回推薦
    print("\n--- Case 1: Initial Recommendation ---")
    test_profile_1 = {
        'Travel_Style': 'Solo traveler',
        'Travel_Frequency': '3-5 times',
        'Preferred_Destinations': 'Nature/forests'
    }
    recos_1 = engine.get_recommendations(user_profile=test_profile_1)
    print(json.dumps(recos_1, indent=2, ensure_ascii=False))

    # ケース2: 周遊計画中の推薦
    print("\n--- Case 2: Itinerary-based Recommendation ---")
    test_profile_2 = {
        'Travel_Style': 'Family traveler',
        'Travel_Frequency': '1-2 times',
        'Preferred_Destinations': 'Parks' # この値が学習データに存在しない場合、handle_unknown='ignore'が機能する
    }
    current_itinerary = ['spot_012']
    recos_2 = engine.get_recommendations(user_profile=test_profile_2, itinerary=current_itinerary)
    print(json.dumps(recos_2, indent=2, ensure_ascii=False))