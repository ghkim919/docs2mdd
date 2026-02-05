"""파일 시스템 감시 모듈"""

import logging
import time
from pathlib import Path
from typing import Callable

from watchdog.events import FileCreatedEvent, FileSystemEventHandler
from watchdog.observers import Observer

from .config import Config
from .converter import ConversionResult, Converter, DocxConverter, PDFConverter

logger = logging.getLogger(__name__)


class ConversionHandler(FileSystemEventHandler):
    """파일 생성 이벤트를 처리하는 핸들러"""

    # 파일 안정화 대기 설정
    STABILITY_CHECK_INTERVAL = 0.5  # 체크 간격 (초)
    STABILITY_CHECK_COUNT = 3       # 연속 체크 횟수
    MAX_WAIT_TIME = 30.0            # 최대 대기 시간 (초)

    def __init__(self, config: Config, converters: list[Converter]):
        self.config = config
        self.converters = converters
        self._on_converted: Callable[[Path, Path], None] | None = None

    def on_created(self, event: FileCreatedEvent) -> None:
        """파일 생성 이벤트 처리"""
        if event.is_directory:
            return

        file_path = Path(event.src_path)
        logger.info(f"새 파일 감지: {file_path}")

        # 지원하는 확장자인지 확인
        if file_path.suffix.lower() not in self.config.supported_extensions:
            logger.debug(f"지원하지 않는 확장자: {file_path.suffix}")
            return

        # 적절한 변환기 찾기
        converter = self._find_converter(file_path)
        if not converter:
            logger.warning(f"변환기를 찾을 수 없음: {file_path}")
            return

        # 파일이 완전히 쓰여질 때까지 대기
        if not self._wait_for_file_ready(file_path):
            logger.error(f"파일 안정화 대기 실패: {file_path}")
            return

        try:
            self._process_file(file_path, converter)
        except Exception as e:
            logger.error(f"변환 실패: {file_path} - {e}")

    def _wait_for_file_ready(self, file_path: Path) -> bool:
        """
        파일이 완전히 쓰여질 때까지 대기

        파일 크기가 연속으로 동일하면 쓰기 완료로 판단
        """
        logger.debug(f"파일 안정화 대기 중: {file_path}")

        stable_count = 0
        last_size = -1
        elapsed = 0.0

        while elapsed < self.MAX_WAIT_TIME:
            try:
                if not file_path.exists():
                    logger.warning(f"파일이 사라짐: {file_path}")
                    return False

                current_size = file_path.stat().st_size

                # 파일이 비어있으면 아직 쓰기 중
                if current_size == 0:
                    stable_count = 0
                elif current_size == last_size:
                    stable_count += 1
                    if stable_count >= self.STABILITY_CHECK_COUNT:
                        logger.debug(f"파일 안정화 완료: {file_path} ({current_size} bytes)")
                        return True
                else:
                    stable_count = 0

                last_size = current_size

            except OSError as e:
                logger.warning(f"파일 상태 확인 실패: {e}")
                stable_count = 0

            time.sleep(self.STABILITY_CHECK_INTERVAL)
            elapsed += self.STABILITY_CHECK_INTERVAL

        logger.warning(f"파일 안정화 타임아웃: {file_path}")
        return False

    def _find_converter(self, file_path: Path) -> Converter | None:
        """파일에 적합한 변환기 찾기"""
        for converter in self.converters:
            if converter.can_handle(file_path):
                return converter
        return None

    def _process_file(self, file_path: Path, converter: Converter) -> None:
        """파일 변환 및 저장"""
        # 상대 경로 계산 (src 기준)
        relative_path = file_path.relative_to(self.config.src_dir)

        # 출력 디렉토리 결정 (파일명으로 디렉토리 생성)
        # src/docs/report.pdf -> dest/docs/report/
        output_dir = self.config.dest_dir / relative_path.parent / file_path.stem
        output_dir.mkdir(parents=True, exist_ok=True)

        # 변환 실행
        result: ConversionResult = converter.convert(file_path)

        # Markdown 파일 저장
        md_path = output_dir / f"{file_path.stem}.md"
        md_path.write_text(result.markdown, encoding="utf-8")
        logger.info(f"Markdown 저장: {md_path}")

        # 에셋 저장
        if result.has_assets:
            assets_dir = output_dir / self.config.assets_dirname
            assets_dir.mkdir(exist_ok=True)

            for asset in result.assets:
                asset_path = assets_dir / asset.filename
                asset_path.write_bytes(asset.data)
                logger.debug(f"에셋 저장: {asset_path}")

            logger.info(f"에셋 {len(result.assets)}개 저장 완료")

        if self._on_converted:
            self._on_converted(file_path, output_dir)


class FileWatcher:
    """파일 시스템 감시자"""

    def __init__(self, config: Config):
        self.config = config
        self.converters: list[Converter] = [PDFConverter(), DocxConverter()]
        self.observer = Observer()
        self.handler = ConversionHandler(config, self.converters)

    def start(self) -> None:
        """감시 시작"""
        self.config.ensure_directories()

        self.observer.schedule(
            self.handler,
            str(self.config.src_dir),
            recursive=True,
        )
        self.observer.start()
        logger.info(f"파일 감시 시작: {self.config.src_dir}")

    def stop(self) -> None:
        """감시 중지"""
        self.observer.stop()
        self.observer.join()
        logger.info("파일 감시 중지")

    def is_alive(self) -> bool:
        """감시자가 실행 중인지 확인"""
        return self.observer.is_alive()

    def process_existing_files(self) -> None:
        """기존 파일들 처리 (시작 시 한 번 실행)"""
        logger.info("기존 파일 검사 중...")

        for ext in self.config.supported_extensions:
            for file_path in self.config.src_dir.rglob(f"*{ext}"):
                # 이미 변환된 파일인지 확인
                relative_path = file_path.relative_to(self.config.src_dir)
                output_dir = self.config.dest_dir / relative_path.parent / file_path.stem
                md_path = output_dir / f"{file_path.stem}.md"

                if md_path.exists():
                    # 원본이 더 최신인 경우에만 재변환
                    if file_path.stat().st_mtime <= md_path.stat().st_mtime:
                        logger.debug(f"이미 변환됨 (스킵): {file_path}")
                        continue

                logger.info(f"기존 파일 변환: {file_path}")
                converter = self.handler._find_converter(file_path)
                if converter:
                    self.handler._process_file(file_path, converter)
