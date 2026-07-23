# 전자세금계산서 발행 자동화

## 현재 구현 및 검증 결과

- Google Sheet 발행대장 생성
- 필수값, 사업자번호, 이메일, 금액 합계 검증
- 동일 거래처·작성일·품목·공급가액 기준 중복 감지
- 상태가 `발행승인`이고 오류와 중복이 없는 행만 발행 후보로 선정
- Sheet 행을 팝빌 `Taxinvoice`/`TaxinvoiceDetail` 객체로 변환
- 팝빌 테스트 API 인증 성공
- 테스트 환경 전자세금계산서 임시저장 및 조회 성공 (`stateCode=100`)
- 운영 SDK 환경은 `is_test=false`로 전환 완료
- 실제 발행은 승인 토큰·운영 환경·법적 발행 확인 플래그의 다중 게이트로 계속 차단
- 발행완료 건의 팝빌 상태와 국세청 승인번호를 30분마다 발행대장에 동기화
- `원본메일ID`가 연결된 발행 건은 발행 후 Gmail 회신 초안을 만들고, 전자세금계산서 확인용 사본·사업자등록증·통장사본을 첨부
- 동일 스레드에 기존 초안이나 더 최신의 발신 메일이 있으면 새 초안을 만들지 않음

## 확인된 팝빌 상태

- 운영 전환 완료
- 운영 환경 API 연결 정상
- 운영 환경 단가: 100원/건
- 운영 환경 파트너 포인트: 10,000원
- 일반 팝빌 잔액이 아니라 파트너 연동 API에서 차감되는 `getPartnerBalance` 기준으로 확인
- 공동인증서 등록 확인, 만료일: 2027-07-20 23:59:59
- 운영 관리자 계정 확인: 오대용

## 실제 발행 전 필수 작업

1. 팝빌 파트너 포인트 충전
2. 발행대장에 거래처·작성일·금액 등 필수값 입력
3. 검증 통과 후 상태를 `발행승인`으로 변경
4. 생성된 승인 토큰과 후보 요약을 Den이 건별 확인
5. Den의 명시적 최종 승인 후에만 운영 발행 명령 실행

## 운영 상태

- `검토대기`: 입력 중 또는 검토 전
- `발행승인`: Den이 발행을 승인한 상태
- `발행완료`: 팝빌 발행 성공 후 자동 기록 예정
- `발행실패`: API 오류 또는 국세청 전송 오류

## 검증 및 운영 명령

```bash
cd ~/automation/tax-invoice

# 전체 자동 테스트
.venv/bin/python -m unittest discover -s tests -v

# 팝빌 테스트·운영 준비 상태(읽기 전용)
.venv/bin/python check_readiness.py

# 실제 Google Sheet 검증(읽기 전용)
.venv/bin/python validate_live.py

# 발행승인 행 미리보기 및 현재 후보에 묶인 승인 토큰 생성(읽기 전용)
.venv/bin/python issue_approved.py

# 발행완료 건의 팝빌·국세청 최신 상태 미리보기/반영
.venv/bin/python sync_issued.py
.venv/bin/python sync_issued.py --write

# 특정 발행 건의 회신 초안 미리보기/생성
.venv/bin/python post_issue_draft.py --request-id '<요청ID>' --source-message-id '<Gmail 메시지 ID>'
.venv/bin/python post_issue_draft.py --request-id '<요청ID>' --source-message-id '<Gmail 메시지 ID>' --create-draft
```

실제 운영 발행은 Den이 미리보기의 거래처·작성일·금액을 확인하고 명시적으로 승인한 뒤에만 실행한다. 실행에는 후보 데이터 스냅샷에서 생성한 토큰과 두 개의 안전 플래그가 모두 필요하다.

```bash
.venv/bin/python issue_approved.py \
  --execute \
  --environment production \
  --approval-token '<현재 미리보기 토큰>' \
  --i-understand-legal-issuance
```

발행 성공 시 Sheet의 `상태`, `검증결과`, `팝빌문서번호`, `국세청승인번호`를 기록한다. 같은 요청ID는 팝빌 문서번호로 재조회하여 중복 발행을 막는다. 후보 행이 바뀌면 승인 토큰도 달라져 이전 승인이 무효화된다. 후속 회신 연결에는 `원본메일ID`, `회신초안ID`, `후속처리` 열을 사용하며 Gmail 초안은 생성만 하고 자동 전송하지 않는다.

## 팝빌 연동에 필요한 값

- LinkID
- SecretKey
- 팝빌에 가입한 공급자 사업자번호
- 팝빌 관리자 아이디(UserID)
- 테스트/운영 전환 승인

자격증명은 코드나 Google Sheet에 저장하지 않고 `~/.hermes/integrations/popbill/credentials.json`에 mode 0600으로 저장한다.
