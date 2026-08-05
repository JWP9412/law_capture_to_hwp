# 버전 출시 체크리스트

버전을 올릴 때마다 아래를 **모두** 수행한 뒤 커밋·푸시한다.

1. [ ] `config.py` 의 `APP_VERSION` 수정 (예: `"1.0.0"`)
2. [ ] `00.CHANGELOG/CHANGELOG_vX.Y.Z.md` **신규** 작성 (기존 파일 덮어쓰기 금지)
3. [ ] `00.README/README_vX.Y.Z.md` **신규** 작성
4. [ ] `00.PROJECT_STRUCTURE/PROJECT_STRUCTURE_vX.Y.Z.md` **신규** 작성
5. [ ] 루트 `README.md` 갱신 (최신 사용법·버전 안내)
6. [ ] 커밋 메시지 한국어, 인코딩 주의
7. [ ] 원격 저장소에 푸시 (요청 시에만)
8. [ ] (선택) GitHub Release / 태그 `vX.Y.Z` 생성
