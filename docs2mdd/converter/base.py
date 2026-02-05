"""변환기 베이스 클래스"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Asset:
    """추출된 에셋 (이미지 등)"""
    filename: str      # 저장될 파일명 (예: img_001.png)
    data: bytes        # 바이너리 데이터
    mime_type: str     # MIME 타입 (예: image/png)


@dataclass
class ConversionResult:
    """변환 결과"""
    markdown: str                          # 변환된 Markdown 내용
    assets: list[Asset] = field(default_factory=list)  # 추출된 에셋 목록

    @property
    def has_assets(self) -> bool:
        return len(self.assets) > 0


class Converter(ABC):
    """문서 변환기 추상 클래스"""

    # 지원하는 확장자 목록 (서브클래스에서 정의)
    supported_extensions: list[str] = []

    @abstractmethod
    def convert(self, file_path: Path) -> ConversionResult:
        """
        파일을 Markdown으로 변환

        Args:
            file_path: 변환할 파일 경로

        Returns:
            ConversionResult: 변환된 Markdown과 에셋 목록
        """
        pass

    @classmethod
    def can_handle(cls, file_path: Path) -> bool:
        """이 변환기가 해당 파일을 처리할 수 있는지 확인"""
        return file_path.suffix.lower() in cls.supported_extensions
