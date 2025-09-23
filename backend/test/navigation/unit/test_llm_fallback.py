from backend.worker.app.services.llm import generator

def test_generate_for_spot__fallbacks_to_description_when_no_context(monkeypatch):
    spot = {
        "spot_id": "A",
        "name": "法体の滝",
        "description": "落差57mの名瀑。映画ロケ地としても知られる。"
    }

    # コンテキスト0件を強制
    monkeypatch.setattr(generator, "retrieve_context", lambda spot_id, lang: [], raising=True)
    # LLM 呼び出しは、渡された prompt をそのまま返すダミーに（プロンプトに description が含まれることを検証）
    monkeypatch.setattr(generator, "generate_text", lambda prompt: prompt, raising=True)

    out = generator.generate_for_spot(spot, lang="ja", style="narration")
    assert "落差57m" in out or "名瀑" in out  # description の要点が含まれること
