import os
import json
import pickle
import faiss
import numpy as np
import pandas as pd
from sklearn.preprocessing import OneHotEncoder

class Recommender:
    """
    学習済みモデルとデータをロードし、ユーザープロファイルに基づいて
    観光スポットの推薦リストを生成するクラス。
    """
    def __init__(self, data_dir='backend/worker/agent_app/processed'):
        print("Initializing Recommender...")
        self.data_dir = data_dir
        self._load_data()
        print("Recommender initialized successfully.")

    def _load_data(self):
        """推薦に必要なモデルとデータをすべてロードする"""
        try:
            self.spot_info = self._load_json('spot_info.json')
            self.travel_matrix = self._load_json('travel_matrix.json')
            self.persona_recommendations = self._load_json('persona_recommendations.json')
            self.spot_id_map = self._load_json('spot_id_map.json')
            
            self.faiss_index = faiss.read_index(os.path.join(self.data_dir, 'spot_embeddings.faiss'))
            
            model_payload = self._load_pickle('persona_model.pkl')
            self.persona_model = model_payload['kmeans_model']
            self.encoder = model_payload['encoder']
            
            self.int_to_spot_id = {v: k for k, v in self.spot_id_map.items()}
        except FileNotFoundError as e:
            print(f"[ERROR] Failed to load recommendation data: {e}")
            print("Please ensure all processed data files exist in the specified directory.")
            raise

    def _load_json(self, filename):
        path = os.path.join(self.data_dir, filename)
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _load_pickle(self, filename):
        path = os.path.join(self.data_dir, filename)
        with open(path, 'rb') as f:
            return pickle.load(f)

    def get_recommendations(self, user_profile, itinerary=None, top_n=3):
        """
        ペルソナ分類、候補生成、フィルタリング、ランキングを行い、
        最終的な推薦リストを返す。

        Args:
            user_profile (dict): ユーザーの属性情報 (age, travel_styleなど)
            itinerary (list, optional): 現在の周遊計画に入っているspot_idのリスト
            top_n (int, optional): 返す推薦リストの最大数

        Returns:
            list: 推薦スポット情報の辞書のリスト
        """
        if itinerary is None:
            itinerary = []

        # 1. ペルソナ分類
        try:
            processed_profile = self._preprocess_profile(user_profile)
            persona_id = self.persona_model.predict(processed_profile)[0]
            print(f"User classified into persona: {persona_id}")
        except Exception as e:
            print(f"[WARN] Failed to classify persona: {e}. Falling back to default.")
            persona_id = 0 # フォールバックとしてペルソナ0を利用

        scores = {}

        # 2. 候補生成 (ペルソナベース & 近傍ベース)
        # ペルソナに基づく推薦
        persona_recos = self.persona_recommendations.get(str(persona_id), [])
        for spot_id in persona_recos:
            scores.setdefault(spot_id, {'score': 0.0, 'reasons': set()})
            scores[spot_id]['score'] += 1.0
            scores[spot_id]['reasons'].add('persona_match')

        # 現在地周辺の推薦 (旅程に最後のスポットがあれば)
        if itinerary:
            last_spot = itinerary[-1]
            if last_spot in self.travel_matrix:
                # 移動時間が短い順にソート
                nearby_spots = sorted(self.travel_matrix[last_spot].items(), key=lambda item: item[1].get('minutes', float('inf')))
                for spot_id, travel_info in nearby_spots[:10]: # 上位10件を候補に
                    scores.setdefault(spot_id, {'score': 0.0, 'reasons': set()})
                    # 近いほどスコアを高くする (例: 60分以内なら加点)
                    if travel_info.get('minutes', 61) <= 60:
                        scores[spot_id]['score'] += 0.5
                        scores[spot_id]['reasons'].add('nearby')

        # 3. フィルタリング (旅程に既に入っているものを除外)
        for spot_id in itinerary:
            if spot_id in scores:
                del scores[spot_id]

        # 4. ランキング
        sorted_spots = sorted(scores.items(), key=lambda item: item[1]['score'], reverse=True)

        # 5. 出力形式に変換
        recommendations = []
        for spot_id, data in sorted_spots[:top_n]:
            recommendations.append({
                "spot_id": spot_id,
                "score": data['score'],
                "reason": list(data['reasons'])
            })
        
        return recommendations

    def _preprocess_profile(self, user_profile):
        """入力されたuser_profileをモデルが予測できる形式に変換する"""
        # 学習時の特徴量の順序を定義
        # Note: 本来は学習時に使用したものを外部から注入するのが望ましい
        features_order = self.encoder.feature_names_in_
        
        profile_df = pd.DataFrame([user_profile])
        # 不足しているカラムをNoneで埋める
        for col in features_order:
            if col not in profile_df.columns:
                profile_df[col] = None
        
        # 順序を揃える
        profile_df = profile_df[features_order]
        
        # OneHotEncoderで変換
        return self.encoder.transform(profile_df)
