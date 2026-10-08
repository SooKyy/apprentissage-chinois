import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import Sentence, UserWord
from app.services import assist, llm


def test_everything_but_health_and_login_requires_a_token(db):
    anonymous = TestClient(app)
    assert anonymous.get("/api/health").json() == {"status": "ok"}
    for method, path in [("get", "/api/stats"), ("get", "/api/review/queue"), ("get", "/api/words/search?q=a"),
                         ("get", "/api/tts?text=你好"), ("post", "/api/assist/explain"), ("get", "/api/settings"),
                         ("get", "/api/auth/me"), ("get", "/api/triage"), ("get", "/api/listen")]:
        assert getattr(anonymous, method)(path).status_code == 401, path
    assert anonymous.post("/api/auth/login", json={"password": "nope"}).status_code == 401
    forged = {"Authorization": "Bearer 9999999999.AAAA"}
    assert anonymous.get("/api/stats", headers=forged).status_code == 401


def test_expired_token_is_rejected(db, monkeypatch):
    from app import security

    monkeypatch.setattr(security.time, "time", lambda: 0)
    token = security.create_access_token()
    monkeypatch.undo()
    assert TestClient(app).get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


@pytest.mark.parametrize(
    ("query", "first"),
    [("吃", "吃"), ("chi", "吃"), ("chī fàn", "吃饭"), ("chifan", "吃饭"), ("nupengyou", "女朋友"),
     ("nvpengyou", "女朋友"), ("manger", "吃"), ("girlfriend", "女朋友"), ("東西", "东西"), ("lv", "绿")],
)
def test_search_by_hanzi_pinyin_and_meaning(client, query, first):
    results = client.get("/api/words/search", params={"q": query}).json()
    assert results and results[0]["simp"] == first, [r["simp"] for r in results]


def test_search_hanzi_lists_exact_then_prefix_then_contains(client):
    assert [r["simp"] for r in client.get("/api/words/search", params={"q": "吃"}).json()] == ["吃", "吃饭", "难吃"]
    assert client.get("/api/words/search", params={"q": "%"}).json() == []


def test_triage_goes_by_frequency_and_skips_proper_nouns_and_sorted_words(client, word):
    simps = [w["simp"] for w in client.get("/api/triage").json()["words"]]
    assert simps == ["的", "吃", "东西", "女朋友", "喜欢", "吃饭", "绿"]
    client.put(f"/api/words/{word('的').id}/status", json={"status": "known", "source": "tri"})
    client.put(f"/api/words/{word('吃').id}/status", json={"status": "learning", "source": "tri"})
    data = client.get("/api/triage").json()
    assert [w["simp"] for w in data["words"]] == ["东西", "女朋友", "喜欢", "吃饭", "绿"] and data["remaining"] == 5
    assert [w["simp"] for w in client.get("/api/triage", params={"hsk": 2}).json()["words"]] == ["绿"]
    assert [w["simp"] for w in client.get("/api/triage", params={"after_rank": 6}).json()["words"]] == ["吃饭", "绿"]
    client.delete(f"/api/words/{word('的').id}/status")
    assert client.get("/api/triage").json()["words"][0]["simp"] == "的"


def test_full_review_flow_with_undo(client, word):
    client.put(f"/api/words/{word('吃').id}/status", json={"status": "learning"})
    queue = client.get("/api/review/queue").json()
    assert queue["counts"]["new"] == 1
    card = queue["cards"][0]
    assert card["kind"] == "reco" and card["is_new"] and card["word"]["simp"] == "吃"
    assert set(card["intervals"]) == {"1", "2", "3", "4"}
    assert client.post(f"/api/review/{card['id']}", json={"rating": 4}).json()["state"] == 2
    assert client.get("/api/review/queue").json()["cards"] == []
    assert client.get("/api/stats").json()["reviews_today"] == 1
    restored = client.post("/api/review/undo").json()
    assert restored["id"] == card["id"] and restored["is_new"]
    assert client.get("/api/stats").json()["reviews_today"] == 0
    assert client.post("/api/review/undo").status_code == 404
    assert client.post(f"/api/review/{card['id']}", json={"rating": 5}).status_code == 422
    assert client.post("/api/review/999999", json={"rating": 3}).status_code == 404
    client.put(f"/api/words/{word('吃').id}/status", json={"status": "known"})
    assert client.post(f"/api/review/{card['id']}", json={"rating": 3}).status_code == 409


def test_stats_streak_coverage_and_counts(client, word):
    client.put(f"/api/words/{word('吃').id}/status", json={"status": "learning"})
    client.put(f"/api/words/{word('的').id}/status", json={"status": "known"})
    card = client.get("/api/review/queue").json()["cards"][0]
    client.post(f"/api/review/{card['id']}", json={"rating": 3})
    stats = client.get("/api/stats").json()
    assert stats["words"] == {"learning": 1, "known": 1, "ignored": 0}
    assert stats["streak"] == 1 and stats["reviews_today"] == 1 and stats["retention_30d"] is None
    assert len(stats["history"]) == 14 and len(stats["forecast"]) == 7
    top500 = stats["coverage"][0]
    assert top500 == {"top": 500, "total": 7, "known": 1, "learning": 1, "ignored": 0}  # 中国 exclu


def test_placement_estimates_and_only_marks_untouched_words_as_known(client, db, word):
    sample = client.get("/api/placement").json()
    assert {w["simp"] for w in sample} == {"的", "吃", "东西", "女朋友", "喜欢", "吃饭", "绿"}
    client.put(f"/api/words/{word('吃').id}/status", json={"status": "learning"})
    answers = [{"word_id": w["id"], "known": w["simp"] in ("的", "吃", "东西")} for w in sample]
    result = client.post("/api/placement", json={"answers": answers}).json()
    assert result["bands"] == [{"from": 1, "to": 250, "tested": 7, "known": 3, "ratio": 0.43}]
    assert result["out_of"] == 7 and result["suggested_after_rank"] == 0
    statuses = {entry.word.simp: (entry.status, entry.source) for entry in db.query(UserWord)}
    assert statuses == {"的": ("known", "placement"), "东西": ("known", "placement"), "吃": ("learning", "dico")}


def test_settings_validation(client):
    assert client.get("/api/settings").json()["new_per_day"] == 12
    assert client.put("/api/settings", json={"new_per_day": 20, "card_kinds": ["prod", "reco"]}).json()["card_kinds"] == ["reco", "prod"]
    for bad in ({"new_per_day": -1}, {"new_per_day": True}, {"desired_retention": 0.99}, {"card_kinds": []},
                {"card_kinds": ["x"]}, {"unknown": 1}, {"auto_enrich": "yes"}, {"tts_rate": 3}):
        assert client.put("/api/settings", json=bad).status_code == 422, bad
    assert client.get("/api/settings").json()["new_per_day"] == 20


def test_enrich_keeps_only_sentences_containing_the_word_and_runs_once(client, db, word, monkeypatch):
    calls = []

    def fake(system, user, **kwargs):
        calls.append(user)
        return {"fr": " manger ", "note": "", "phrases": [
            {"zh": "你想吃什么？", "fr": "Tu veux manger quoi ?"},
            {"zh": "我们走吧。", "fr": "Allons-y."},
            {"zh": "你想吃什么？", "fr": "doublon"},
            {"zh": "我吃了。", "fr": ""},
            "n'importe quoi",
        ]}

    monkeypatch.setattr(llm, "chat_json", fake)
    data = client.post(f"/api/words/{word('吃').id}/enrich").json()
    assert data["llm_fr"] == "manger" and data["llm_note"] is None and data["enriched"]
    assert data["sentences"] == [{"id": data["sentences"][0]["id"], "zh": "你想吃什么？", "pinyin": "nǐ xiǎng chī shén me？", "fr": "Tu veux manger quoi ?"}]
    client.post(f"/api/words/{word('吃').id}/enrich")
    assert len(calls) == 1 and "吃" in calls[0] and db.query(Sentence).count() == 1


def test_llm_failures_surface_as_502_and_leave_the_word_untouched(client, word):
    response = client.post(f"/api/words/{word('吃').id}/enrich")  # pas de clé en test
    assert response.status_code == 502 and "OPENROUTER_API_KEY" in response.json()["detail"]
    assert not client.get(f"/api/words/{word('吃').id}").json()["enriched"]
    assert client.post("/api/assist/explain", json={"text": "bonjour"}).status_code == 422
    assert client.post("/api/assist/correct", json={"text": "我喜欢吃"}).status_code == 502


def test_explain_links_words_to_the_dictionary(client, word, monkeypatch):
    monkeypatch.setattr(llm, "chat_json", lambda *a, **k: {
        "traduction": "J'aime manger.", "litteral": "je aimer manger",
        "mots": [{"zh": "喜欢", "sens": "aimer"}, {"zh": "吃", "sens": "manger"}, {"zh": "abc", "sens": "?"}, {"zh": "嘻嘻", "sens": "hihi"}],
        "grammaire": [{"point": "喜欢 + V", "explication": "aimer faire"}, {"point": "", "explication": "vide"}],
        "registre": "neutre"})
    client.put(f"/api/words/{word('吃').id}/status", json={"status": "known"})
    data = client.post("/api/assist/explain", json={"text": "我喜欢吃"}).json()
    assert data["pinyin"] == "wǒ xǐ huan chī"
    assert [(m["zh"], m["pinyin"], m["status"], m["word_id"] is not None) for m in data["mots"]] == [
        ("喜欢", "xǐ huan", None, True), ("吃", "chī", "known", True), ("嘻嘻", "xī xī", None, False)]
    assert data["grammaire"] == [{"point": "喜欢 + V", "explication": "aimer faire"}]


def test_correct_is_only_flagged_correct_without_errors(db, monkeypatch):
    monkeypatch.setattr(llm, "chat_json", lambda *a, **k: {"correct": True, "corrige": "我喜欢吃。", "naturel": "",
        "traduction": "J'aime manger.", "erreurs": [{"original": "x", "correction": "y", "explication": "z"}]})
    data = assist.correct(db, "我喜欢吃", "")
    assert data["correct"] is False and data["naturel"] == "我喜欢吃。" and data["corrige_pinyin"] == "wǒ xǐ huan chī。"


def test_tts_rejects_text_without_chinese(client):
    assert client.get("/api/tts", params={"text": "hello"}).status_code == 422
    assert client.get("/api/tts", params={"text": "好" * 201}).status_code == 422


def test_listen_only_uses_sentences_of_words_i_study(client, db, word):
    from app.services.clock import utcnow

    for simp in ("吃", "绿"):
        db.add(Sentence(word_id=word(simp).id, zh=f"{simp}。", pinyin="x", fr="x", created_at=utcnow()))
    db.commit()
    assert client.get("/api/listen").json() == []
    client.put(f"/api/words/{word('吃').id}/status", json={"status": "learning"})
    assert [s["zh"] for s in client.get("/api/listen").json()] == ["吃。"]
