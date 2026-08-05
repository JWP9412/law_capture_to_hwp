# PROJECT_STRUCTURE v1.0.0

법령 조문 캡처 → 한글 삽입 자동화 (`law_capture`) 폴더 구조.

```
law_capture_to_hwp/
├── 법령캡처_실행.pyw          # 더블클릭 실행
├── main.py                    # 창 시작점
├── config.py                  # 설정·APP_VERSION
├── run_from_command_line.py   # CLI 실행
├── README.md                  # 최신 사용법
├── 인수인계.md
├── 설치목록.md
├── user_favorites.json        # 사용자 즐겨찾기 (gitignore 권장)
│
├── core/                      # 화면을 모름 — 실제 기능
│   ├── law_source.py          # 검색·연혁·시점별 판
│   ├── law_site.py            # 법령정보센터 HTTP
│   ├── law_pdf.py             # Playwright PDF
│   ├── article_number.py      # 조문 번호 해석·추정
│   ├── article_text.py        # 미리보기·전체보기 글자
│   ├── favorites.py           # 즐겨찾기 JSON
│   ├── annotate.py            # 밑줄·캡처
│   ├── hwp_insert.py          # 한글 삽입
│   ├── version_series.py      # 개정본 비교·캡션
│   ├── pipeline.py            # 전체 파이프라인
│   ├── models.py
│   └── errors.py
│
├── ui/                        # 법령·한글을 모름 — 화면만
│   ├── app_window.py
│   ├── input_view.py
│   ├── preview_view.py
│   ├── favorites_dialog.py    # 즐겨찾기 설정 창
│   ├── progress_view.py
│   ├── result_view.py
│   ├── controller.py          # UI ↔ core
│   ├── theme.py
│   └── widgets.py
│
├── spike/                     # 검증 스크립트 (한글 켜는 것 주의)
├── out/                       # 결과·중간 파일 (gitignore)
├── logs/                      # 로그 (gitignore)
│
├── docs/
│   └── VERSION_RELEASE_CHECKLIST.md
├── 00.README/
│   └── README_v1.0.0.md
├── 00.CHANGELOG/
│   └── CHANGELOG_v1.0.0.md
└── 00.PROJECT_STRUCTURE/
    └── PROJECT_STRUCTURE_v1.0.0.md
```

## 계층 규칙

- `core/` 는 UI를 모른다. 실패 시 `core/errors.py` 예외.
- `ui/` 는 법령·한글 API를 모른다. `controller.py` 만 둘을 잇는다.
- 예외를 잡아 조문별로 계속 진행하는 곳은 `pipeline.run_capture_jobs` 한 곳.
