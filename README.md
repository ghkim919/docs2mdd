# docs2mdd

문서(Docs)를 마크다운(Markdown)으로 자동 변환하는 데몬 서비스

## 📌 프로젝트 소개

`docs2mdd`는 지정된 소스 디렉토리를 감시하며, 문서 파일이 추가되면 자동으로 Markdown으로 변환하여 대상 디렉토리에 저장합니다.

```
src/                              dest/
├── report.pdf            →      ├── report/
│                                 │   ├── report.md
│                                 │   └── assets/
│                                 │       └── img_001.png
```

## 🚀 기능

- [x] PDF → Markdown 변환 (이미지 추출 포함)
- [ ] Word(.docx) → Markdown 변환
- [ ] HTML → Markdown 변환
- [x] 파일 시스템 실시간 감시
- [x] 디렉토리 구조 유지
- [x] 데몬 모드 지원

## 🛠️ 설치

```bash
# 저장소 클론
git clone https://github.com/ghkim919/docs2mdd.git
cd docs2mdd

# 의존성 설치
pip install -e .

# 또는 개발 모드
pip install -e ".[dev]"
```

## 📖 사용법

### 초기 설정

```bash
# 현재 디렉토리에 config.yaml 및 src/, dest/ 디렉토리 생성
docs2mdd init
```

### 데몬 실행

```bash
# 데몬 시작
docs2mdd start

# 포그라운드에서 실행 (디버깅용)
docs2mdd start -f

# 데몬 상태 확인
docs2mdd status

# 데몬 중지
docs2mdd stop

# 데몬 재시작
docs2mdd restart
```

### 단일 파일 변환

```bash
# 단일 파일 변환 (데몬 없이)
docs2mdd convert document.pdf

# 출력 디렉토리 지정
docs2mdd convert document.pdf -o ./output
```

### 설정 파일 (config.yaml)

```yaml
# 소스 디렉토리 (감시할 디렉토리)
src_dir: "./src"

# 목적지 디렉토리 (변환된 파일 저장 위치)
dest_dir: "./dest"

# 지원 확장자
supported_extensions:
  - ".pdf"

# 에셋 디렉토리 이름
assets_dirname: "assets"

# 로깅 설정
logging:
  level: "INFO"  # DEBUG, INFO, WARNING, ERROR
  file: null     # 로그 파일 경로

# 데몬 설정
daemon:
  pid_file: "/tmp/docs2mdd.pid"
  poll_interval: 1.0
```

## 📦 의존성

- Python >= 3.9
- watchdog - 파일 시스템 감시
- PyMuPDF - PDF 처리
- PyYAML - 설정 파일 파싱
- click - CLI 인터페이스

## 📄 라이선스

MIT License
