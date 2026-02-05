# docs2mdd

[English](README.md)

문서(Docs)를 마크다운(Markdown)으로 자동 변환하는 데몬 서비스

## 프로젝트 소개

`docs2mdd`는 지정된 소스 디렉토리를 감시하며, 문서 파일이 추가되면 자동으로 Markdown으로 변환하여 대상 디렉토리에 저장합니다.

```
src/                              dest/
├── report.pdf            →      ├── report/
│                                 │   ├── report.md
│                                 │   └── assets/
│                                 │       └── img_001.png
```

## 기능

- [x] PDF → Markdown 변환 (이미지 추출 포함)
- [x] Word (.docx) → Markdown 변환
- [x] PowerPoint (.pptx) → Markdown 변환 (슬라이드별 구분)
- [x] Excel (.xlsx) → Markdown 변환 (시트별 테이블)
- [x] 한글 (.hwpx) → Markdown 변환
- [x] HTML → Markdown 변환
- [x] **URL fetch**: URL에서 HTML 다운로드 후 Markdown 변환
- [x] **Frontmatter 메타데이터**: 문서 메타데이터 자동 추출 (제목, 작성자, 날짜 등)
- [x] 파일 시스템 실시간 감시
- [x] 디렉토리 구조 유지
- [x] 데몬 모드 지원

## 설치

```bash
# 저장소 클론
git clone https://github.com/ghkim919/docs2mdd.git
cd docs2mdd

# 의존성 설치
pip install -e .

# 또는 개발 모드
pip install -e ".[dev]"
```

## 사용법

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
docs2mdd convert document.docx
docs2mdd convert document.pptx
docs2mdd convert document.xlsx
docs2mdd convert document.hwpx

# 출력 디렉토리 지정
docs2mdd convert document.pdf -o ./output
```

### URL에서 변환

```bash
# URL에서 HTML 다운로드 후 Markdown으로 변환
docs2mdd fetch https://example.com/article.html

# 출력 디렉토리 지정
docs2mdd fetch https://example.com -o ./output

# 출력 파일명 지정
docs2mdd fetch https://example.com -n my_article
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
  - ".docx"
  - ".pptx"
  - ".xlsx"
  - ".hwpx"
  - ".html"
  - ".htm"

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

## 의존성

- Python >= 3.9
- watchdog - 파일 시스템 감시
- PyMuPDF - PDF 처리
- python-docx - Word 문서 처리
- python-pptx - PowerPoint 처리
- openpyxl - Excel 처리
- beautifulsoup4 - HTML 파싱
- markdownify - HTML → Markdown 변환
- PyYAML - 설정 파일 파싱
- click - CLI 인터페이스

## 제한 사항

### HWPX (한글) 포맷
- **이미지 추출이 완벽하지 않을 수 있습니다**: HWPX는 한컴의 독자 포맷으로, 내부 구조가 공식 문서화되어 있지 않습니다. 문서 버전과 작성 방식에 따라 이미지 참조 방식이 달라 일부 이미지가 추출되지 않을 수 있습니다.
- **테이블은 지원**되지만, 복잡한 병합 셀은 정확히 표현되지 않을 수 있습니다.
- 최상의 결과를 위해 한글에서 PDF 또는 DOCX로 내보내기 후 변환하는 것을 권장합니다.

## 라이선스

MIT License
