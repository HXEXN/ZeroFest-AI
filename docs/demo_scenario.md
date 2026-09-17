# 3–5분 심사 Demo Scenario

> 화면에 표시되는 모든 수치와 효과는 **Demo Simulation / Sample / Synthetic Data**이며 실제 실증 결과가 아니다.

## 0:00–0:40 · 문제와 차별성

시작 화면에서 `Data → Predict → Decide → Human Approval → Demand Change → Re-predict`를 짚는다.

발표 문장: “ZeroFest는 남은 음식을 처리하는 서비스가 아니라, 남을 재고를 예측하고 운영과 학생 수요를 함께 움직여 남지 않도록 만드는 플랫폼입니다.”

## 0:40–1:30 · Admin

1. `학생회 Control Tower`를 연다.
2. A구역 닭꼬치의 현재 재고 180개, 예상 잔여 70개, HIGH를 확인한다.
3. 근거인 최근 판매 감소, 1시간 뒤 강수 80%, 메인 공연 종료를 보여준다.
4. AI Chat에서 “왜 닭꼬치를 할인해야 돼?”를 실행한다.

## 1:30–2:15 · Operator

1. `부스 운영자`를 연다.
2. 원클릭 판매 입력과 AI Recommendation을 설명한다.
3. `20% 마감 할인`만 승인한다.
4. “AI가 임의 실행하지 않고 운영자가 최종 승인합니다”를 강조한다.

## 2:15–2:50 · Student

1. `학생` 화면에서 닭꼬치 6,000원 → 4,800원 할인을 확인한다.
2. Mock Map의 A구역 혜택을 보여준다.
3. Quiz와 Stamp는 Core AI가 아니라 향후 수요 라우팅 모듈임을 짧게 설명한다.

## 2:50–3:30 · Closed Loop

1. `Before / After`를 연다.
2. `학생 반응 발생 → 재예측`을 누른다.
3. 시뮬레이션 기준 예상 잔여가 70개에서 15개로 낮아지는 것을 보여준다.
4. 실제 판매가 들어오면 같은 파이프라인이 새 상태로 반복된다고 마무리한다.

## 장애 대응

- LLM 키/호출 장애: 실제 DB에 근거한 Local Grounded Chat으로 자동 전환
- Weather API 장애: 버전 관리된 Mock Weather로 자동 전환
- LangGraph import 장애: 동일한 결정론적 노드 순서 fallback
- 데이터가 꼬인 경우: 사이드바 `Demo 전체 초기화` 한 번 클릭

## 기술 질의응답용 화면

`AI · ML · Data Ops`에서 2023–2025 과거 이력 Adapter, 2025 시간 Hold-out, Feature Importance, Model Run, LangGraph Action Queue를 확인한다. 모든 품질·성능 값은 합성 데이터 결과임을 함께 설명한다.
