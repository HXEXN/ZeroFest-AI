# Stitch UI/UX 적용 명세

제공된 `stitch_zerofest_ai_campus_operations_platform.zip`의 4개 화면과 `ZeroFest AI Eco-Operations OS` 디자인 토큰을 실제 Streamlit 기능 계층에 연결했다. 원본 HTML은 정적 목업이므로 그대로 iframe에 넣지 않고, 상호작용과 데이터 상태는 Python/SQLite를 단일 Source of Truth로 유지했다.

## 화면 연결

| Stitch Reference | Streamlit 화면 | 실제 연결 기능 |
|---|---|---|
| 통합 게이트웨이 | `app.py` | 역할별 분리 진입, 실시간 데모 상태, 데이터 출처 경고 |
| 관리자 관제 | `pages/admin.py` | 부스별 예측·위험·Agent Action·Copilot 즉시 진입 |
| AI 운영 대화 | `pages/chat.py` | 전체/부스 범위, 빠른 질문, 근거 공개, 실행권한 분리 |
| Booth Fast POS | `pages/operator.py` | 56px 터치 입력, 실재고 교정, 승인 할인·종료 |
| 학생 모바일 | `pages/student.py` | 승인 할인, 구역 지도, DB 저장 Quiz·Stamp 보상 |
| AI Engine Core | `pages/ai_ops.py` | 데이터 품질, 학습 파이프라인, 모델 Registry, Agent Audit |

## 인간공학 및 휴먼 인터페이스 원칙

1. **역할 격리**: 관리자, 현장 운영자, 학생, AI 운영자의 과업을 별도 화면으로 분리해 선택 부담을 줄인다.
2. **현장 시인성**: 핵심 숫자는 tabular monospace, 위험도는 색상뿐 아니라 점·텍스트·배지를 함께 사용한다.
3. **운영자 도달성**: 판매/재고/승인 버튼은 최소 56px로 구성하고 주요 Action을 한 화면의 자연스러운 상→하 흐름에 둔다.
4. **오류 예방**: AI Action은 `PENDING` 상태이며 사람의 명시적 승인 없이는 실행되지 않는다.
5. **인지 부하 제어**: Admin은 비교 중심 고밀도, Operator는 큰 버튼 중심 중밀도, Student는 혜택 우선 저밀도로 구성한다.
6. **상태의 직접성**: 승인 직후 학생 가격이 바뀌고, 학생 반응 후 Before/After와 Dashboard가 같은 SQLite 상태를 읽는다.
7. **접근성**: 고대비 Deep Emerald/Slate, 48px 이상 기본 버튼, 키보드 Focus Ring, Reduced Motion 대응을 적용한다.
8. **신뢰 형성**: 예측 근거, 모델 출처, 합성 데이터 경고와 LLM 역할 제한을 행동 지점 가까이에 둔다.
9. **대화 안전성**: Copilot 답변은 현재 DB 스냅샷에서 먼저 생성하고, LLM은 선택적 설명 계층으로만 사용한다. 채팅에는 Action 실행 권한을 주지 않는다.

## Design Tokens

- Primary: `#166534` / Deep Emerald
- Secondary: `#10B981` / Live & Stable
- Promotion: `#F97316` / Flash Action
- Canvas: `#FAF8FF`
- Supporting Surface: `#F2F3FF`, `#EAEDFF`
- Text: `#131B2E`
- Danger / Warning / Stable: `#EF4444` / `#F59E0B` / `#10B981`
- Panel radius: 16px, nested controls: 8–12px, status badges: full pill

색상만으로 상태를 전달하지 않으며 HIGH/MEDIUM/LOW 텍스트와 설명을 항상 병기한다.
