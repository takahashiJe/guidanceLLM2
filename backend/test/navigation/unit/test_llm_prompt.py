from backend.worker.app.services.llm.prompt import build_prompt

def test_build_prompt__contains_language_style_and_spot():
    spot = {"spot_id":"A", "name":"丸池様", "description":"透明度の高い湧水池。"}
    ctx = [{"text":"鳥海山の湧水と湿原についての解説"}, {"text":"保全のルール"}]
    prompt = build_prompt(spot, ctx, lang="ja", style="narration")

    assert "ja" in prompt or "日本語" in prompt  # 言語指定が入っている
    assert "narration" in prompt or "ナレーション" in prompt  # スタイル指定
    assert "丸池" in prompt or "丸池様" in prompt  # スポット名が入る
    # 参照文脈の要素が含まれる
    assert "湿原" in prompt or "ルール" in prompt
