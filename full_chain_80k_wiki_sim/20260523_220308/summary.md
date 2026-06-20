# Full Chain 80k Wiki Simulation

- started_at: 20260523_220308
- novel_id: 144
- title: 回声雾港
- target_chars: 50000
- target_chapter_chars: 2500
- expected_chapters: 20
- expected_volumes: 3
- expected_ranges: [{'volume': 1, 'minChapter': 1, 'maxChapter': 6}, {'volume': 2, 'minChapter': 7, 'maxChapter': 13}, {'volume': 3, 'minChapter': 14, 'maxChapter': 20}]
- generated_chars: 57511
- generated_chinese_chars: 51152
- fail_count: 1
- warn_count: 14

| stage | status | elapsed(s) | notes |
|---|---:|---:|---|
| template | 200 | 132.0 | chars=5262 |
| create_novel | 200 | 0.07 |  |
| novel_info_after_create | 200 | 0.03 |  |
| upload_worldbuilding | 200 | 0.06 |  |
| persist_topology | 200 | 0.38 |  |
| wiki_status_after_worldbuilding | 200 | 0.03 |  |
| wiki_continuity_after_worldbuilding | 200 | 0.17 |  |
| wiki_search_after_worldbuilding_回声层 | 200 | 0.04 |  |
| wiki_search_after_worldbuilding_声纹盐 | 200 | 0.01 |  |
| wiki_search_after_worldbuilding_雾钟 | 200 | 0.0 |  |
| summary | 200 | 128.09 |  |
| save_summary | 200 | 0.02 |  |
| finalize_summary | 200 | 0.03 |  |
| wiki_status_after_summary | 200 | 0.05 |  |
| wiki_continuity_after_summary | 200 | 0.05 |  |
| wiki_search_after_summary_回声层 | 200 | 0.03 |  |
| wiki_search_after_summary_声纹盐 | 200 | 0.01 |  |
| wiki_search_after_summary_雾钟 | 200 | 0.03 |  |
| outline | 200 | 145.91 |  |
| save_outline | 200 | 0.03 |  |
| finalize_outline | 200 | 0.03 |  |
| wiki_status_after_outline | 200 | 0.04 |  |
| wiki_continuity_after_outline | 200 | 0.06 |  |
| wiki_search_after_outline_回声层 | 200 | 0.03 |  |
| wiki_search_after_outline_声纹盐 | 200 | 0.01 |  |
| wiki_search_after_outline_雾钟 | 200 | 0.0 |  |
| detail_outline_v1 | 200 | 46.75 |  |
| chapters_v1 | 200 | 0.04 |  |
| save_detail_v1 | 200 | 0.05 |  |
| finalize_detail_v1 | 200 | 0.05 |  |
| wiki_status_after_detail_v1 | 200 | 0.05 |  |
| wiki_continuity_after_detail_v1 | 200 | 0.05 |  |
| wiki_search_after_detail_v1_回声层 | 200 | 0.01 |  |
| wiki_search_after_detail_v1_声纹盐 | 200 | 0.02 |  |
| wiki_search_after_detail_v1_雾钟 | 200 | 0.02 |  |
| finalized_chapters_v1 | 200 | 0.04 |  |
| fetch_saved_chapter_583 | 200 | 0.03 |  |
| finalize_text_583 | 200 | 0.03 |  |
| wiki_status_after_chapter_1 | 200 | 60.07 |  |
| wiki_continuity_after_chapter_1 | 200 | 39.47 |  |
| wiki_search_after_chapter_1_回声层 | 200 | 0.02 |  |
| wiki_search_after_chapter_1_声纹盐 | 200 | 0.03 |  |
| wiki_search_after_chapter_1_雾钟 | 200 | 0.01 |  |
| fetch_saved_chapter_584 | 200 | 0.03 |  |
| finalize_text_584 | 200 | 0.03 |  |
| wiki_status_after_chapter_2 | 200 | 60.05 |  |
| wiki_continuity_after_chapter_2 | 200 | 35.9 |  |
| wiki_search_after_chapter_2_回声层 | 200 | 0.03 |  |
| wiki_search_after_chapter_2_声纹盐 | 200 | 0.03 |  |
| wiki_search_after_chapter_2_雾钟 | 200 | 0.0 |  |
| fetch_saved_chapter_585 | 200 | 0.02 |  |
| finalize_text_585 | 200 | 0.05 |  |
| wiki_status_after_chapter_3 | 200 | 60.07 |  |
| wiki_continuity_after_chapter_3 | 200 | 14.5 |  |
| wiki_search_after_chapter_3_回声层 | 200 | 0.03 |  |
| wiki_search_after_chapter_3_声纹盐 | 200 | 0.01 |  |
| wiki_search_after_chapter_3_雾钟 | 200 | 0.01 |  |
| fetch_saved_chapter_586 | 200 | 0.03 |  |
| finalize_text_586 | 200 | 0.04 |  |
| wiki_status_after_chapter_4 | 200 | 60.07 |  |
| wiki_continuity_after_chapter_4 | 200 | 15.66 |  |
| wiki_search_after_chapter_4_回声层 | 200 | 0.03 |  |
| wiki_search_after_chapter_4_声纹盐 | 200 | 0.03 |  |
| wiki_search_after_chapter_4_雾钟 | 200 | 0.02 |  |
| fetch_saved_chapter_587 | 200 | 0.04 |  |
| finalize_text_587 | 200 | 0.03 |  |
| wiki_status_after_chapter_5 | 200 | 60.07 |  |
| wiki_continuity_after_chapter_5 | 200 | 29.29 |  |
| wiki_search_after_chapter_5_回声层 | 200 | 0.03 |  |
| wiki_search_after_chapter_5_声纹盐 | 200 | 0.03 |  |
| wiki_search_after_chapter_5_雾钟 | 200 | 0.03 |  |
| fetch_saved_chapter_588 | 200 | 0.04 |  |
| finalize_text_588 | 200 | 0.05 |  |
| wiki_status_after_chapter_6 | 200 | 60.04 |  |
| wiki_continuity_after_chapter_6 | 200 | 42.51 |  |
| wiki_search_after_chapter_6_回声层 | 200 | 0.03 |  |
| wiki_search_after_chapter_6_声纹盐 | 200 | 0.03 |  |
| wiki_search_after_chapter_6_雾钟 | 200 | 0.01 |  |
| detail_outline_v2 | 200 | 45.66 |  |
| chapters_v2 | 200 | 0.03 |  |
| save_detail_v2 | 200 | 0.07 |  |
| finalize_detail_v2 | 200 | 0.05 |  |
| wiki_status_after_detail_v2 | 200 | 0.05 |  |
| wiki_continuity_after_detail_v2 | 200 | 0.07 |  |
| wiki_search_after_detail_v2_回声层 | 200 | 0.03 |  |
| wiki_search_after_detail_v2_声纹盐 | 200 | 0.02 |  |
| wiki_search_after_detail_v2_雾钟 | 200 | 0.02 |  |
| finalized_chapters_v2 | 200 | 0.02 |  |
| fetch_saved_chapter_589 | 200 | 0.03 |  |
| finalize_text_589 | 200 | 0.04 |  |
| wiki_status_after_chapter_7 | 200 | 60.05 |  |
| wiki_continuity_after_chapter_7 | 200 | 12.76 |  |
| wiki_search_after_chapter_7_回声层 | 200 | 0.03 |  |
| wiki_search_after_chapter_7_声纹盐 | 200 | 0.02 |  |
| wiki_search_after_chapter_7_雾钟 | 200 | 0.03 |  |
| fetch_saved_chapter_590 | 200 | 0.04 |  |
| finalize_text_590 | 200 | 0.03 |  |
| wiki_status_after_chapter_8 | 200 | 60.06 |  |
| wiki_continuity_after_chapter_8 | 200 | 32.45 |  |
| wiki_search_after_chapter_8_回声层 | 200 | 0.01 |  |
| wiki_search_after_chapter_8_声纹盐 | 200 | 0.0 |  |
| wiki_search_after_chapter_8_雾钟 | 200 | 0.03 |  |
| fetch_saved_chapter_591 | 200 | 0.05 |  |
| finalize_text_591 | 200 | 0.03 |  |
| wiki_status_after_chapter_9 | 200 | 60.08 |  |
| wiki_continuity_after_chapter_9 | 200 | 7.14 |  |
| wiki_search_after_chapter_9_回声层 | 200 | 0.03 |  |
| wiki_search_after_chapter_9_声纹盐 | 200 | 0.03 |  |
| wiki_search_after_chapter_9_雾钟 | 200 | 0.03 |  |
| fetch_saved_chapter_592 | 200 | 0.05 |  |
| finalize_text_592 | 200 | 0.05 |  |
| wiki_status_after_chapter_10 | 200 | 60.05 |  |
| wiki_continuity_after_chapter_10 | 200 | 36.22 |  |
| wiki_search_after_chapter_10_回声层 | 200 | 0.02 |  |
| wiki_search_after_chapter_10_声纹盐 | 200 | 0.02 |  |
| wiki_search_after_chapter_10_雾钟 | 200 | 0.03 |  |
| fetch_saved_chapter_593 | 200 | 0.04 |  |
| finalize_text_593 | 200 | 0.03 |  |
| wiki_status_after_chapter_11 | 200 | 60.06 |  |
| wiki_continuity_after_chapter_11 | 200 | 22.89 |  |
| wiki_search_after_chapter_11_回声层 | 200 | 0.01 |  |
| wiki_search_after_chapter_11_声纹盐 | 200 | 0.01 |  |
| wiki_search_after_chapter_11_雾钟 | 200 | 0.03 |  |
| fetch_saved_chapter_594 | 200 | 0.04 |  |
| finalize_text_594 | 200 | 0.05 |  |
| wiki_status_after_chapter_12 | 200 | 60.04 |  |
| wiki_continuity_after_chapter_12 | 200 | 41.57 |  |
| wiki_search_after_chapter_12_回声层 | 200 | 0.01 |  |
| wiki_search_after_chapter_12_声纹盐 | 200 | 0.03 |  |
| wiki_search_after_chapter_12_雾钟 | 200 | 0.0 |  |
| fetch_saved_chapter_595 | 200 | 0.04 |  |
| finalize_text_595 | 200 | 0.05 |  |
| wiki_status_after_chapter_13 | 200 | 60.05 |  |
| wiki_continuity_after_chapter_13 | 200 | 31.96 |  |
| wiki_search_after_chapter_13_回声层 | 200 | 0.01 |  |
| wiki_search_after_chapter_13_声纹盐 | 200 | 0.03 |  |
| wiki_search_after_chapter_13_雾钟 | 200 | 0.01 |  |
| detail_outline_v3 | 200 | 49.47 |  |
| chapters_v3 | 200 | 0.04 |  |
| save_detail_v3 | 200 | 0.06 |  |
| finalize_detail_v3 | 200 | 0.06 |  |
| wiki_status_after_detail_v3 | 200 | 0.05 |  |
| wiki_continuity_after_detail_v3 | 200 | 0.1 |  |
| wiki_search_after_detail_v3_回声层 | 200 | 0.02 |  |
| wiki_search_after_detail_v3_声纹盐 | 200 | 0.01 |  |
| wiki_search_after_detail_v3_雾钟 | 200 | 0.02 |  |
| finalized_chapters_v3 | 200 | 0.02 |  |
| fetch_saved_chapter_596 | 200 | 0.04 |  |
| finalize_text_596 | 200 | 0.03 |  |
| wiki_status_after_chapter_14 | 200 | 60.05 |  |
| wiki_continuity_after_chapter_14 | 200 | 24.63 |  |
| wiki_search_after_chapter_14_回声层 | 200 | 0.01 |  |
| wiki_search_after_chapter_14_声纹盐 | 200 | 0.02 |  |
| wiki_search_after_chapter_14_雾钟 | 200 | 0.0 |  |
| fetch_saved_chapter_597 | 200 | 0.04 |  |
| finalize_text_597 | 200 | 0.04 |  |
| wiki_status_after_chapter_15 | 200 | 60.04 |  |
| wiki_continuity_after_chapter_15 | 200 | 39.69 |  |
| wiki_search_after_chapter_15_回声层 | 200 | 0.03 |  |
| wiki_search_after_chapter_15_声纹盐 | 200 | 0.03 |  |
| wiki_search_after_chapter_15_雾钟 | 200 | 0.0 |  |
| fetch_saved_chapter_598 | 200 | 0.04 |  |
| finalize_text_598 | 200 | 0.05 |  |
| wiki_status_after_chapter_16 | 200 | 60.07 |  |
| wiki_continuity_after_chapter_16 | 200 | 14.46 |  |
| wiki_search_after_chapter_16_回声层 | 200 | 0.01 |  |
| wiki_search_after_chapter_16_声纹盐 | 200 | 0.03 |  |
| wiki_search_after_chapter_16_雾钟 | 200 | 0.03 |  |
| fetch_saved_chapter_599 | 200 | 0.03 |  |
| finalize_text_599 | 200 | 0.02 |  |
| wiki_status_after_chapter_17 | 200 | 60.04 |  |
| wiki_continuity_after_chapter_17 | 200 | 2.62 |  |
| wiki_search_after_chapter_17_回声层 | 200 | 0.02 |  |
| wiki_search_after_chapter_17_声纹盐 | 200 | 0.0 |  |
| wiki_search_after_chapter_17_雾钟 | 200 | 0.03 |  |
| fetch_saved_chapter_600 | 200 | 0.04 |  |
| finalize_text_600 | 200 | 0.04 |  |
| wiki_status_after_chapter_18 | 200 | 60.04 |  |
| wiki_continuity_after_chapter_18 | 200 | 42.96 |  |
| wiki_search_after_chapter_18_回声层 | 200 | 0.02 |  |
| wiki_search_after_chapter_18_声纹盐 | 200 | 0.03 |  |
| wiki_search_after_chapter_18_雾钟 | 200 | 0.03 |  |
| fetch_saved_chapter_601 | 200 | 0.03 |  |
| finalize_text_601 | 200 | 0.05 |  |
| wiki_status_after_chapter_19 | 200 | 60.03 |  |
| wiki_continuity_after_chapter_19 | 200 | 29.23 |  |
| wiki_search_after_chapter_19_回声层 | 200 | 0.02 |  |
| wiki_search_after_chapter_19_声纹盐 | 200 | 0.03 |  |
| wiki_search_after_chapter_19_雾钟 | 200 | 0.03 |  |
| fetch_saved_chapter_602 | 200 | 0.04 |  |
| finalize_text_602 | 200 | 0.05 |  |
| wiki_status_after_chapter_20 | 200 | 60.05 |  |
| wiki_continuity_after_chapter_20 | 200 | 35.06 |  |
| wiki_search_after_chapter_20_回声层 | 200 | 0.03 |  |
| wiki_search_after_chapter_20_声纹盐 | 200 | 0.0 |  |
| wiki_search_after_chapter_20_雾钟 | 200 | 0.01 |  |

## Chapters
- ch001 v1 id=583 chars=2904 cn=2613 first=141.57s elapsed=170.3s wiki_terms= domain_terms=声纹,回声,旧港,频率,金属 overlap=
- ch002 v1 id=584 chars=3174 cn=2827 first=42.43s elapsed=93.4s wiki_terms= domain_terms=声纹,回声,雾港,旧港,低频,频率 overlap=0.1152
- ch003 v1 id=585 chars=3448 cn=3088 first=46.09s elapsed=97.91s wiki_terms= domain_terms=声纹,回声,旧港,频率,金属 overlap=0.0468
- ch004 v1 id=586 chars=2794 cn=2477 first=83.56s elapsed=121.27s wiki_terms= domain_terms=声纹,旧港,频率 overlap=0.0434
- ch005 v1 id=587 chars=2946 cn=2622 first=58.32s elapsed=100.7s wiki_terms= domain_terms=声纹,回声,旧港,低频,频率,金属 overlap=0.0463
- ch006 v1 id=588 chars=2046 cn=1818 first=89.23s elapsed=110.9s wiki_terms= domain_terms=声纹,旧港,频率,管道 overlap=0.028
- ch007 v2 id=589 chars=2918 cn=2576 first=39.02s elapsed=77.99s wiki_terms= domain_terms=声纹,回声,雾港,旧港,频率,管道 overlap=0.0196
- ch008 v2 id=590 chars=3010 cn=2647 first=50.71s elapsed=89.26s wiki_terms= domain_terms=旧港,低频,频率,金属,盐,管道 overlap=0.0417
- ch009 v2 id=591 chars=2718 cn=2406 first=94.66s elapsed=121.93s wiki_terms= domain_terms=旧港,频率,共鸣 overlap=0.0357
- ch010 v2 id=592 chars=3146 cn=2756 first=56.23s elapsed=95.52s wiki_terms= domain_terms=声纹,回声,雾港,旧港,低频,频率 overlap=0.0434
- ch011 v2 id=593 chars=3014 cn=2628 first=79.51s elapsed=120.74s wiki_terms= domain_terms=声纹,旧港,频率,金属,管道 overlap=0.0315
- ch012 v2 id=594 chars=2774 cn=2457 first=78.84s elapsed=115.35s wiki_terms= domain_terms=声纹,旧港,频率,金属,管道 overlap=0.035
- ch013 v2 id=595 chars=2972 cn=2670 first=135.5s elapsed=166.09s wiki_terms= domain_terms=回声,雾港,旧港,低频,频率 overlap=0.0346
- ch014 v3 id=596 chars=2695 cn=2388 first=48.82s elapsed=86.85s wiki_terms= domain_terms=声纹,雾港,旧港,频率 overlap=0.0586
- ch015 v3 id=597 chars=2880 cn=2557 first=114.76s elapsed=145.97s wiki_terms= domain_terms=声纹,雾港,旧港,频率,金属 overlap=0.0829
- ch016 v3 id=598 chars=3186 cn=2872 first=55.43s elapsed=99.97s wiki_terms= domain_terms=声纹,雾港,旧港,频率,金属,管道 overlap=0.0518
- ch017 v3 id=599 chars=3036 cn=2727 first=73.8s elapsed=114.37s wiki_terms= domain_terms=声纹,回声,雾港,旧港,频率,金属 overlap=0.0609
- ch018 v3 id=600 chars=2675 cn=2427 first=58.54s elapsed=96.24s wiki_terms= domain_terms=声纹,回声,雾港,旧港,频率,金属 overlap=0.0332
- ch019 v3 id=601 chars=2509 cn=2270 first=114.69s elapsed=142.03s wiki_terms= domain_terms=声纹,回声,雾港,旧港,频率,金属 overlap=0.0638
- ch020 v3 id=602 chars=2666 cn=2326 first=50.33s elapsed=89.77s wiki_terms= domain_terms=声纹,回声,雾港,旧港,频率,金属 overlap=0.0317

## Wiki
- after_worldbuilding: docs=1 chapters=0 foreshadows=0
- after_summary: docs=1 chapters=0 foreshadows=0
- after_outline: docs=1 chapters=0 foreshadows=0
- after_detail_v1: docs=1 chapters=0 foreshadows=0
- after_chapter_1: docs=None chapters=None foreshadows=None
- after_chapter_2: docs=None chapters=None foreshadows=None
- after_chapter_3: docs=None chapters=None foreshadows=None
- after_chapter_4: docs=None chapters=None foreshadows=None
- after_chapter_5: docs=None chapters=None foreshadows=None
- after_chapter_6: docs=None chapters=None foreshadows=None
- after_detail_v2: docs=1 chapters=6 foreshadows=42
- after_chapter_7: docs=None chapters=None foreshadows=None
- after_chapter_8: docs=None chapters=None foreshadows=None
- after_chapter_9: docs=None chapters=None foreshadows=None
- after_chapter_10: docs=None chapters=None foreshadows=None
- after_chapter_11: docs=None chapters=None foreshadows=None
- after_chapter_12: docs=None chapters=None foreshadows=None
- after_chapter_13: docs=None chapters=None foreshadows=None
- after_detail_v3: docs=1 chapters=13 foreshadows=81
- after_chapter_14: docs=None chapters=None foreshadows=None
- after_chapter_15: docs=None chapters=None foreshadows=None
- after_chapter_16: docs=None chapters=None foreshadows=None
- after_chapter_17: docs=None chapters=None foreshadows=None
- after_chapter_18: docs=None chapters=None foreshadows=None
- after_chapter_19: docs=None chapters=None foreshadows=None
- after_chapter_20: docs=None chapters=None foreshadows=None