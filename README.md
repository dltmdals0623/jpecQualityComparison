# jpegQualityComparison

**동일한 PNG 원본을 JPEG 품질(quality) 5~100 구간으로 저장하며, 용량·PSNR·SSIM이 어떻게 변하는지 측정하고 "단순한 이미지"와 "복잡한 이미지"의 차이를 비교하는 실험 코드입니다.**

4K(3840×2160) PNG 두 장(`simple.png`, `complex.png`)을 기준으로, JPEG 품질을 5단위로 바꿔 가며 압축한 뒤 원본 대비 화질 지표와 파일 크기 비율을 CSV로 저장하고 그래프로 시각화합니다. 파이프라인은 JPEG 변환·측정 → CSV 저장 → 두 이미지 비교 그래프 생성 순서로 동작합니다.

---

## 1. 실험 개요

- **목적**: JPEG 품질 설정값에 따른 압축률과 화질 손실을 정량 비교하고, 이미지 복잡도에 따라 그 경향이 어떻게 달라지는지 확인
- **입력 이미지**: `images/simple.png` (약 5.1 MiB), `images/complex.png` (약 10.8 MiB), 모두 3840×2160
- **품질 설정**: `quality = 100, 95, 90, … , 5` (5단위, 총 20단계)
- **측정 지표**

| 지표 | 설명 |
| --- | --- |
| `size_percent_of_png` | JPEG 파일 크기 ÷ 원본 PNG 크기 × 100 (%) |
| `PSNR_dB` | 최대 신호 대 잡음비. 높을수록 원본과 가까움 (`data_range=255`) |
| `SSIM` | 구조적 유사도 (0~1, 1에 가까울수록 원본과 유사) |
| `bpp` | 픽셀당 비트 수 (비교용 CSV에 포함) |

- **공정한 비교를 위한 고정 조건**
  - 모든 JPEG는 매번 **원본에서 각각** 저장 (재압축 누적 없음)
  - 색차 서브샘플링 `subsampling=0`(4:4:4), `optimize=False`, `progressive=False` 고정
  - RGB 8비트(0~255) 기준으로 비교하며, 알파 채널은 지정 배경색(기본 흰색)에 합성
  - PSNR은 원본과 완전히 같으면 `inf`로 기록하고, 그래프에서는 해당 지점을 제외

## 2. 저장소 구조

```bash
jpecQualityComparison/
├── jpegQualityCompare.py   # 이미지 1장에 대해 품질별 JPEG 생성 → PSNR/SSIM/용량 측정 → CSV·그래프 저장
├── graphing.py             # simple/complex 두 CSV를 불러와 비교 그래프(개별 3종 + 통합 1종) 생성
├── images/                 # 실험 원본 PNG
│    ├── simple.png         # 단순한 이미지 (3840×2160)
│    └── complex.png        # 복잡한 이미지 (3840×2160)
├── results/                # 품질별로 저장된 JPEG 결과물 (예: complex_quality_005.jpg ~ _100.jpg)
├── comparison/             # 두 이미지 비교 결과
│    ├── qualityComparison.csv      # simple/complex 지표와 차이값을 한 표로 병합한 CSV
│    ├── 00_combined_3metrics.png   # 세 지표를 독립 y축으로 겹쳐 그린 통합 그래프
│    ├── 01_size_percent.png        # 용량 비율 비교
│    ├── 02_psnr.png                # PSNR 비교
│    └── 03_ssim.png                # SSIM 비교
├── LICENSE                 # MIT License
└── .gitignore
```

### 동작 흐름

**`jpegQualityCompare.py`**

1. 입력 파일이 PNG(8비트 RGB/회색조/팔레트, 비애니메이션)인지 검증하고, EXIF 방향 보정 후 RGB로 변환합니다.
2. 품질 100부터 5까지 5씩 낮추며 JPEG를 저장하고, 다시 디코딩하여 원본 배열과 비교합니다.
3. `scikit-image`로 PSNR·SSIM을 계산합니다. SSIM 윈도 크기는 `min(7, 가로, 세로)`(짝수면 -1)로 자동 조정합니다.
4. 품질·해상도·바이트 수·PNG 대비 비율·PSNR·SSIM을 CSV(`utf-8-sig`)로 저장하고 단일 이미지용 3축 그래프를 그립니다.

**`graphing.py`**

1. 두 CSV의 필수 열, 값 범위(품질 0~100, SSIM -1~1), 중복·결측 여부를 검증합니다.
2. 지표별 개별 그래프 3장(`01`~`03`)과 세 지표를 독립 y축으로 겹친 통합 그래프(`00`)를 저장합니다.
3. 색은 이미지별(Simple=빨강 계열, Complex=파랑 계열), 선 스타일은 지표별(실선/파선/점선)로 구분합니다.

## 3. 실행 환경

- Python 3
- 필수 패키지: [`pillow`](https://python-pillow.org), [`numpy`](https://numpy.org), [`scikit-image`](https://scikit-image.org), [`matplotlib`](https://matplotlib.org), [`pandas`](https://pandas.pydata.org) (`graphing.py`용)

```bash
pip install pillow numpy scikit-image matplotlib pandas
```

## 4. 사용 방법

### 4.1 이미지별 JPEG 품질 측정

```bash
python jpegQualityCompare.py images/simple.png  --output results
python jpegQualityCompare.py images/complex.png --output results
```

- `--output`: 결과 저장 폴더 (기본값 `jpeg_results`)
- `--background R G B`: 투명 영역을 합성할 배경색 (기본값 `255 255 255`)
- 실행하면 품질별 `.jpg`, 비교 기준 `reference_rgb.png`, `*_quality_metrics.csv`, 그래프가 저장되고 터미널에 품질별 `Size(KiB)`, `PSNR(dB)`, `SSIM` 표가 출력됩니다.

### 4.2 simple vs. complex 비교 그래프 생성

```bash
python graphing.py
# 경로 지정 시
python graphing.py --simple results/simple_quality_metrics.csv \
                   --complex results/complex_quality_metrics.csv \
                   --output comparison
```

- 기본 입력은 `results/simple_quality_metrics.csv`, `results/complex_quality_metrics.csv`이며 그래프 4장이 `comparison/`에 저장됩니다.

> 참고: 입력 경로를 그대로 파일명에 사용하므로, 결과 파일명이 `simple_quality_metrics.csv`처럼 나오게 하려면 `images/` 폴더로 이동한 상태에서 실행하거나 파일명 규칙을 확인해 주세요.

## 5. 실험 결과 요약 (`comparison/qualityComparison.csv`)

| quality | 용량(PNG 대비 %) simple / complex | PSNR (dB) simple / complex | SSIM simple / complex |
| ---: | :---: | :---: | :---: |
| 5 | 4.25 / 2.20 | 32.91 / 27.25 | 0.978 / 0.772 |
| 25 | 4.37 / 3.45 | 45.16 / 36.24 | 0.990 / 0.902 |
| 50 | 4.49 / 5.05 | 49.18 / 39.05 | 0.993 / 0.938 |
| 75 | 4.70 / 7.84 | 51.26 / 41.54 | 0.994 / 0.961 |
| 90 | 5.59 / 14.76 | 51.63 / 44.55 | 0.994 / 0.978 |
| 95 | 10.70 / 22.42 | 51.92 / 46.30 | 0.993 / 0.985 |
| 100 | 60.33 / 66.51 | 51.42 / 51.68 | 0.992 / 0.995 |

## 6. 관찰 내용

- **단순한 이미지**는 품질 5~85 구간에서 JPEG 용량이 약 223~258 KiB로 거의 일정하고, 품질 90 이후에 급격히 증가합니다. SSIM은 품질 5에서도 0.978로 높게 유지됩니다.
- **복잡한 이미지**는 품질이 오를수록 용량이 꾸준히 커지고(5: 약 242 KiB → 100: 약 7,322 KiB), 같은 품질에서도 PSNR은 약 5~10 dB, SSIM은 최대 0.2 정도 낮아 압축 손실이 더 크게 나타납니다.
- 두 이미지 모두 품질 100에서는 JPEG가 PNG 대비 60%대 크기로 커져, **품질 90~95 부근이 용량 대비 화질 효율이 좋은 구간**으로 보입니다.
- 단순한 이미지의 PSNR은 품질 95(51.92 dB) 부근에서 최대이고 품질 100(51.42 dB)에서 오히려 소폭 낮아지는 등 단조 증가하지 않는 구간이 있습니다. 이 수치는 이 실험 이미지와 인코더 설정(4:4:4)에 한정된 결과입니다.
- 통합 그래프의 세 y축은 서로 독립된 눈금이므로, 곡선의 높이나 교차 지점을 지표 간에 직접 비교하면 안 됩니다.

## 6. 라이선스

[MIT License](LICENSE) © 2026 dltmdals
