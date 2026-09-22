# day.stock

일봉 차트와 수급으로 익일 급등 후보를 골라 평일 15:10 카카오톡으로 보내는 저장소.

## 동작

평일 15:10 에 카카오톡으로 종가 매수 후 익일 시가 매도 기대수익이 높은 종목을 보낸다. 데이터는 이 저장소 `surge_data/` 에만 저장한다. aut.stock 은 3년치 수급을 읽어 오는 용도로만 쓰고 그쪽에는 쓰지 않는다.

1. 15:00 세션 루틴이 `surge/run_request.txt` 를 갱신해 푸시한다
2. GitHub Actions (`.github/workflows/surge.yml`) 가 `python -m surge.live` 를 실행한다
   - 네이버 증권에서 코스피+코스닥 보통주 일봉 약 3년치 수집 (장중이면 오늘 봉은 현재가 기준)
   - aut.stock 의 3년치 KRX 기관/외국인 수급 패널을 `surge_data/history/krx_panel.parquet` 로 복사해 두고 실행 때마다 새 날짜만 증분 파일로 저장한다 (aut.stock 에는 쓰지 않는다). 15시에는 당일 수급을 모르므로 전일까지 수급만 쓴다
   - 차트 피처 (모멘텀 / 봉 모양 / 거래량 / 이평 정배열 / 신고가 / 변동성 수축) 와 전일 수급으로 익일 시가 수익률을 HistGradientBoosting 회귀로 학습. 기준 선택 근거는 `python -m surge.research` (3년 패널 워크포워드 240일 비교)
   - 점검: 상한가 도달 / 거래대금 10억 미만 / 스팩 / 우선주 제외. 최근 60일 홀드아웃 적중률 계산
   - `surge_data/picks/YYYYMMDD.json` 과 오늘 봉 스냅샷 `surge_data/daily/YYYYMMDD.csv` 를 커밋
3. 세션이 결과를 다시 점검한 뒤 말머리 `[종목 추천]` 으로 카카오톡을 보낸다. 휴장일은 보내지 않는다

## 설치와 실행

```
pip install -r requirements.txt
python -m surge.live --force     # 휴장일에도 마지막 봉으로 추천 (시험용)
python -m surge.research         # 추천 기준 비교 (3년 패널 워크포워드)
```

## 구조

- `surge/naver.py` 네이버 증권 종목 목록과 일봉 수집
- `surge/history.py` aut.stock 3년치 KRX 수급 패널 복사본과 증분 갱신
- `surge/features.py` 차트와 수급 피처
- `surge/model.py` 학습기 (익일 시가 수익률 회귀)
- `surge/live.py` 장중 추천 실행과 점검과 카톡 문구 생성
- `surge/research.py` 추천 기준 비교 연구
- `surge_data/picks/` 날짜별 추천 결과 · `surge_data/daily/` 당일 시세 스냅샷 · `surge_data/history/` 수급 데이터
