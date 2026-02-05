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
class Metadata:
    """문서 메타데이터"""
    title: str | None = None          # 문서 제목
    author: str | None = None         # 작성자
    created: str | None = None        # 생성일
    modified: str | None = None       # 수정일
    pages: int | None = None          # 페이지 수 (PDF)
    slides: int | None = None         # 슬라이드 수 (PPTX)
    sheets: int | None = None         # 시트 수 (XLSX)
    extra: dict = field(default_factory=dict)  # 추가 메타데이터

    def to_frontmatter(self, source: str | None = None) -> str:
        """YAML frontmatter 문자열 생성"""
        lines = ["---"]

        if self.title:
            lines.append(f"title: \"{self.title}\"")
        if self.author:
            lines.append(f"author: \"{self.author}\"")
        if self.created:
            lines.append(f"created: \"{self.created}\"")
        if self.modified:
            lines.append(f"modified: \"{self.modified}\"")
        if self.pages:
            lines.append(f"pages: {self.pages}")
        if self.slides:
            lines.append(f"slides: {self.slides}")
        if self.sheets:
            lines.append(f"sheets: {self.sheets}")
        if source:
            lines.append(f"source: \"{source}\"")
        for key, value in self.extra.items():
            if isinstance(value, str):
                lines.append(f"{key}: \"{value}\"")
            else:
                lines.append(f"{key}: {value}")

        lines.append("---")

        # 메타데이터가 없으면 빈 문자열 반환
        if len(lines) <= 2:
            return ""

        return "\n".join(lines)


@dataclass
class ConversionResult:
    """변환 결과"""
    markdown: str                                       # 변환된 Markdown 내용
    assets: list[Asset] = field(default_factory=list)   # 추출된 에셋 목록
    metadata: Metadata = field(default_factory=Metadata)  # 문서 메타데이터

    @property
    def has_assets(self) -> bool:
        return len(self.assets) > 0

    def to_markdown_with_frontmatter(self, source: str | None = None) -> str:
        """Frontmatter가 포함된 Markdown 반환"""
        frontmatter = self.metadata.to_frontmatter(source)
        if frontmatter:
            return f"{frontmatter}\n\n{self.markdown}"
        return self.markdown


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
