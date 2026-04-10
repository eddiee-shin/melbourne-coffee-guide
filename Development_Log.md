# ☕ 멜번 커피 가이드 개발 일지 (Development Log)

**프로젝트**: 멜번 커피 가이드 (Melbourne Coffee Guide)  
**마지막 업데이트**: 2026-04-10  
**상태**: 데이터 저장 안정성 확보 및 유저 인터페이스 고도화 완료

---

## 🚀 최근 주요 성과 (Recent Achievements)

### 1. 데이터 저장 안정성 확보 (Persistence Robustness) - [NEW]
- **유저 식별자(Viewer ID) 이슈 해결**:
    - 초기화 시점 차이로 인해 `viewerId`가 `undefined`로 누락되던 버그를 수정.
    - `bootstrap` 시점에 식별자를 생성/로드하도록 변경하여 실행 안정성 확보.
- **방어적 코딩 및 디버깅 도구 도입**:
    - 모든 DB 요청 전 식별자 유효성 검사 로직 추가.
    - 전역 변수 `window.MCG_DEBUG`를 통해 콘솔에서 실시간 상태 확인 가능하게 개선.
- **Supabase RLS 정책 완전 복구**:
    - 비로그인 유저(`anon`)의 `SELECT`, `INSERT`, `UPDATE`, `DELETE` 정책을 전면 보강하여 데이터 저장 및 조회가 불가능했던 근본 원인 해결.
    - 특히 `cafe_likes` 테이블의 조회 권한 누락으로 인한 '좋아요 0개' 표시 현상을 완벽히 해결.
- **강력한 브라우저 캐시 무력화**:
    - `index.html`에 동적 타임스탬프 기반 스크립트 로더를 도입하여, 수정 사항이 모든 유저에게 즉시 반영되도록 개선.

### 2. 어드민 시스템 기능 강화 (Admin Feature Enhancement)
- **로컬 사진 업로드 기능 복구**:
    - `admin_server.py`에 이미지 업로드 엔드포인트(`8001/api/admin/upload-image`) 추가.
    - 업로드된 이미지를 로컬 `images/` 폴더에 자동 저장하고, DB의 `image_url`에 즉시 반영하는 로직 구현.
- **이미지 자동 배포 (Automated Git Sync)**:
    - 사진 업로드 성공 시 백엔드에서 즉시 `git add`, `git commit`, `git push`를 자동 수행.
    - 수동 푸시 없이도 깃허브 및 Vercel에 사진이 실시간 반영되도록 자동화.
- **댓글 관리 시스템 도입**:
    - 관리자 페이지 하단에 **'최근 댓글 관리'** 섹션 추가.
    - 모든 카페의 댓글을 한눈에 조회하고, 부적절한 내용을 관리자 권한으로 즉시 삭제할 수 있는 기능 구축.
- **실시간 로그 스트리밍 (Real-time Logging)**:
    - 스크래퍼 구동 로그를 HTTP 스트림 방식으로 프론트엔드에 실시간 전송.
    - 관리자 페이지 내 터미널 스타일의 **실시간 로그 콘솔 UI** 도입.

### 3. 유저 인터페이스(UI) 고도화 (UX Enhancement)
- **가중치 기반 추천 정렬**:
    - **좋아요 수 > 댓글 수 > 구글 리뷰 수** 순의 복합 정렬 로직 적용.
- **정보 시각화**:
    - 카페 카드에 **댓글 총 개수 배지(`💬 N`)**를 추가하여 상호작용 지표를 가시화.

---

## 🛠️ 기술 사양 (Tech Stack)
- **Frontend**: Vanilla JS (ES Modules), HTML5, CSS3, Leaflet.js
- **Backend**: Python 3 (Admin Server), Subprocess streaming
- **Database**: Supabase (PostgreSQL), Aggregated Views (cafes_with_feedback)

---

## 📅 향후 계획 (Future Roadmap)
- [ ] 사용자 위치 기반 '내 주변 카페' 자동 추천 기능
- [ ] 이미지 업로드 최적화 및 안정적인 CDN 연동
- [ ] 관리자 대시보드 내 방문자 통계 그래프 시각화

---
_이 문서는 Antigravity AI에 의해 생성되었으며, 프로젝트의 기술적 자산으로 활용됩니다._
