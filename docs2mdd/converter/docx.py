"""Word (DOCX) 변환기"""

import logging
from pathlib import Path

from docx import Document
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.table import Table
from docx.text.paragraph import Paragraph

from .base import Asset, ConversionResult, Converter, Metadata

logger = logging.getLogger(__name__)


class DocxConverter(Converter):
    """Word 문서를 Markdown으로 변환하는 변환기"""

    supported_extensions = [".docx"]

    def convert(self, file_path: Path) -> ConversionResult:
        """
        DOCX 파일을 Markdown으로 변환

        Args:
            file_path: DOCX 파일 경로

        Returns:
            ConversionResult: 변환된 Markdown과 추출된 이미지
        """
        logger.info(f"DOCX 변환 시작: {file_path}")

        doc = Document(file_path)
        markdown_parts: list[str] = []
        assets: list[Asset] = []
        image_counter = 0

        # 메타데이터 추출
        metadata = self._extract_metadata(doc)

        # 이미지 관계 매핑 (rId -> 이미지 데이터)
        image_map = self._extract_images(doc)

        # 문서 본문 순회
        for element in doc.element.body:
            # 단락 처리
            if element.tag.endswith("p"):
                para = Paragraph(element, doc)
                para_md, new_images = self._process_paragraph(
                    para, image_map, image_counter
                )
                if para_md:
                    markdown_parts.append(para_md)
                    assets.extend(new_images)
                    image_counter += len(new_images)

            # 테이블 처리
            elif element.tag.endswith("tbl"):
                table = Table(element, doc)
                table_md = self._process_table(table)
                if table_md:
                    markdown_parts.append(table_md)

        markdown = "\n\n".join(markdown_parts)
        markdown = self._cleanup_markdown(markdown)

        logger.info(f"DOCX 변환 완료: {len(assets)}개 이미지 추출")

        return ConversionResult(markdown=markdown, assets=assets, metadata=metadata)

    def _extract_metadata(self, doc: Document) -> Metadata:
        """DOCX 메타데이터 추출"""
        props = doc.core_properties

        def format_date(dt) -> str | None:
            if dt:
                return dt.strftime("%Y-%m-%d")
            return None

        return Metadata(
            title=props.title or None,
            author=props.author or None,
            created=format_date(props.created),
            modified=format_date(props.modified),
        )

    def _extract_images(self, doc: Document) -> dict[str, tuple[bytes, str]]:
        """문서에서 이미지 추출하여 rId -> (data, ext) 매핑 반환"""
        image_map = {}

        for rel in doc.part.rels.values():
            if rel.reltype == RT.IMAGE:
                try:
                    image_part = rel.target_part
                    image_data = image_part.blob
                    content_type = image_part.content_type
                    ext = content_type.split("/")[-1]
                    if ext == "jpeg":
                        ext = "jpg"
                    image_map[rel.rId] = (image_data, ext)
                except Exception as e:
                    logger.warning(f"이미지 추출 실패 (rId: {rel.rId}): {e}")

        return image_map

    def _process_paragraph(
        self,
        para: Paragraph,
        image_map: dict[str, tuple[bytes, str]],
        image_counter: int,
    ) -> tuple[str, list[Asset]]:
        """단락을 Markdown으로 변환"""
        assets: list[Asset] = []
        text = para.text.strip()

        # 이미지 확인 (inline 및 anchor 모두 처리)
        for run in para.runs:
            # inline 이미지와 anchor(floating) 이미지 모두 찾기
            drawings = run.element.findall(
                ".//{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}inline"
            ) + run.element.findall(
                ".//{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}anchor"
            )

            for drawing in drawings:
                blip = drawing.find(
                    ".//{http://schemas.openxmlformats.org/drawingml/2006/main}blip"
                )
                if blip is not None:
                    embed = blip.get(
                        "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"
                    )
                    if embed and embed in image_map:
                        image_data, ext = image_map[embed]
                        image_counter += 1
                        filename = f"img_{image_counter:03d}.{ext}"
                        assets.append(
                            Asset(
                                filename=filename,
                                data=image_data,
                                mime_type=f"image/{ext}",
                            )
                        )
                        text += f"\n\n![Image {image_counter}](./assets/{filename})"
                        logger.debug(f"이미지 추출: {filename}")

        if not text and not assets:
            return "", []

        # 스타일 기반 헤딩 변환
        style_name = para.style.name if para.style else ""
        if style_name.startswith("Heading"):
            try:
                level = int(style_name.replace("Heading", "").strip())
                level = min(level, 6)
                text = "#" * level + " " + text
            except ValueError:
                pass
        elif style_name == "Title":
            text = "# " + text

        return text, assets

    def _process_table(self, table: Table) -> str:
        """테이블을 Markdown 테이블로 변환"""
        rows = []

        for row in table.rows:
            cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
            rows.append("| " + " | ".join(cells) + " |")

        if not rows:
            return ""

        # 헤더 구분선 추가 (첫 번째 행 이후)
        if len(rows) >= 1:
            col_count = len(table.rows[0].cells)
            separator = "| " + " | ".join(["---"] * col_count) + " |"
            rows.insert(1, separator)

        return "\n".join(rows)

    def _cleanup_markdown(self, text: str) -> str:
        """Markdown 텍스트 정리"""
        lines = text.split("\n")
        cleaned_lines: list[str] = []

        for line in lines:
            # 연속된 빈 줄 제거 (최대 2줄)
            if not line.strip():
                if cleaned_lines and not cleaned_lines[-1].strip():
                    if len(cleaned_lines) >= 2 and not cleaned_lines[-2].strip():
                        continue
            cleaned_lines.append(line)

        return "\n".join(cleaned_lines).strip()
