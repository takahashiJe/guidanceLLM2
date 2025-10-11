#!/usr/bin/env python3
import os
import shutil

# ====== md_slug → spot_id の対応表 ======
mapping = {
    # --- 前回のPOI.json ---
    "spot_agariko_daio": "spot_001",
    "spot_akata_daibutsu": "spot_002",
    "spot_botsumeki_park": "spot_003",
    "spot_chokai_lake": "spot_005",
    "spot_chokai_panorama_park": "spot_006",
    "spot_hottai_falls": "spot_007",
    "spot_juroku_rakan": "spot_008",
    "spot_kamaiso_spring": "spot_009",
    "spot_naso_shirataki": "spot_010",
    "spot_michinoeki_nemunooka": "spot_011",
    "spot_mototaki": "spot_012",
    "spot_chokai_marimo": "spot_013",
    "spot_nikaho_museum": "spot_014",
    "spot_ryugahara_wetland": "spot_015",
    "spot_ichinotaki_ninotaki": "spot_016",  # ← ここは特例（016と017両方作る）
    "spot_maruike_sama": "spot_018",
    "spot_chokaisan_omonoimi_jinja": "spot_019",
    "spot_kyu_aoyama_hontei": "spot_020",
    "spot_kanmanji_temple": "spot_021",
    "spot_misaki_park": "spot_022",
    "spot_haraigawa_shrine": "spot_024",
    "spot_akataki_falls": "spot_025",
    "spot_dohara_falls": "spot_035",
    "spot_chokai_kogen": "spot_036",
    "spot_kinbo_shrine": "spot_037",
    "spot_nakayama_kasen_park": "spot_039",
    "spot_nasogawa_kasen_park": "spot_040",
    "spot_ushiwatarigawa_baikamo": "spot_042",
    "spot_hanadate_clean_heights": "spot_043",
    # --- 宿泊施設系 ---
    "spot_chokai_kazoku_ryokomura": "spot_004",
    "spot_nishihama_cottage": "spot_023",
    "facility_base_yunodai": "spot_026",
    "facility_base_foresta": "spot_027",
    "facility_base_kizakura_onsen": "spot_028",
    "facility_base_poporokko": "spot_029",
    "facility_base_yurari": "spot_030",
    "facility_hut_ohama": "spot_031",
    "facility_hut_takinokoya": "spot_032",
    "facility_shelter_karashishidaira": "spot_033",
    "facility_shelter_nanatsugama": "spot_034",
    "facility_base_chokaiso": "spot_041",
    "facility_hut_mansuke": "spot_044",
}

# ==== mdファイルが置いてあるディレクトリを指定 ====
# 例: 同じディレクトリで実行するなら '.'
MD_DIR = '.'

for md_slug, spot_id in mapping.items():
    src = os.path.join(MD_DIR, f"{md_slug}.md")
    dst = os.path.join(MD_DIR, f"{spot_id}.md")
    if not os.path.exists(src):
        print(f"[WARN] {src} が見つかりません")
        continue

    # 特例: spot_ichinotaki_ninotaki → spot_016 と spot_017
    if md_slug == "spot_ichinotaki_ninotaki":
        dst1 = os.path.join(MD_DIR, "spot_016.md")
        dst2 = os.path.join(MD_DIR, "spot_017.md")
        shutil.copy2(src, dst1)
        shutil.copy2(src, dst2)
        print(f"[OK] {src} → spot_016.md, spot_017.md")
    else:
        os.rename(src, dst)
        print(f"[OK] {src} → {dst}")
