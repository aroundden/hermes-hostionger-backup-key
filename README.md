# Hermes 상태 백업 — default profile

- 원본 Hermes Home: `/Users/insideden/.hermes`
- 대상 저장소: `aroundden/hermes-hostionger-backup-key`
- 갱신 방식: 의미있는 설정/상태 파일 변경이 있을 때만 새 커밋 생성

## 포함한 것
- `config/config.sanitized.yaml`: Hermes 설정 파일에서 토큰/키/비밀번호성 값을 제거한 사본
- `config/env.keys.txt`: `.env`에 존재하는 환경변수 이름 목록만 포함, 값 제외
- `status/*.txt`: `hermes status/doctor/tools/skills/mcp/cron/profile/plugins` 결과의 민감정보 제거본
- `inventory/hermes-files-manifest.json`: 핵심 Hermes 설정/확장 파일의 파일명/크기/수정시각 목록
- `automation/tax-invoice/`: 세금계산서 자동화의 복구 가능한 소스·테스트·의존성 파일. 발행자 실데이터는 템플릿으로 대체

## 의도적으로 제외한 것
- API 키/PAT/OAuth 토큰/Google 토큰/클라이언트 시크릿
- `state.db`, 세션 전문, 로그 전문
- raw `.env`, `auth.json`, `sessions/`, `logs/`
- 팝빌 자격증명, 발행자 실데이터, 발행 PDF, 사업자등록증·통장사본, 자동화 가상환경·캐시

복원 시에는 이 저장소를 기준으로 설정 구조와 활성화 상태를 확인하고, 실제 비밀값은 각 서비스에서 재발급/재인증하세요.
