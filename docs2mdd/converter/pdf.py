"""PDF 변환기"""

import logging
from pathlib import Path

import fitz  # PyMuPDF

from .base import Asset, ConversionResult, Converter, Metadata

logger = logging.getLogger(__name__)


class PDFConverter(Converter):
    """PDF를 Markdown으로 변환하는 변환기"""

    supported_extensions = [".pdf"]

    def convert(self, file_path: Path) -> ConversionResult:
        """
        PDF 파일을 Markdown으로 변환

        Args:
            file_path: PDF 파일 경로

        Returns:
            ConversionResult: 변환된 Markdown과 추출된 이미지
        """
        logger.info(f"PDF 변환 시작: {file_path}")

        doc = fitz.open(file_path)
        markdown_parts: list[str] = []
        assets: list[Asset] = []
        image_counter = 0

        # 메타데이터 추출
        metadata = self._extract_metadata(doc)

        try:
            for page_num, page in enumerate(doc, start=1):
                # 페이지 구분 주석
                markdown_parts.append(f"\n<!-- Page {page_num} -->\n")

                # 테이블 추출 시도 (PyMuPDF 1.23.0+)
                table_bboxes: list[tuple[float, float, float, float]] = []
                try:
                    tables = page.find_tables()
                    for table in tables:
                        table_md = self._process_table(table)
                        if table_md:
                            markdown_parts.append(table_md)
                            table_bboxes.append(table.bbox)
                except AttributeError:
                    # find_tables를 지원하지 않는 버전
                    pass
                except Exception as e:
                    logger.debug(f"테이블 추출 실패 (page {page_num}): {e}")

                # 텍스트 추출 (테이블 영역 제외)
                if table_bboxes:
                    # 테이블 영역을 제외한 텍스트 블록만 추출
                    text_parts = []
                    blocks = page.get_text("blocks")
                    for block in blocks:
                        block_rect = fitz.Rect(block[:4])
                        in_table = False
                        for table_bbox in table_bboxes:
                            table_rect = fitz.Rect(table_bbox)
                            if block_rect.intersects(table_rect):
                                in_table = True
                                break
                        if not in_table and block[4].strip():
                            text_parts.append(block[4])
                    text = "\n".join(text_parts)
                else:
                    text = page.get_text("text")

                if text.strip():
                    markdown_parts.append(text)

                # 이미지 추출
                image_list = page.get_images(full=True)
                for img_index, img_info in enumerate(image_list):
                    xref = img_info[0]

                    try:
                        base_image = doc.extract_image(xref)
                        image_data = base_image["image"]
                        image_ext = base_image["ext"]
                        mime_type = f"image/{image_ext}"

                        image_counter += 1
                        filename = f"img_{image_counter:03d}.{image_ext}"

                        assets.append(Asset(
                            filename=filename,
                            data=image_data,
                            mime_type=mime_type,
                        ))

                        # Markdown 이미지 링크 추가
                        markdown_parts.append(f"\n![Image {image_counter}](./assets/{filename})\n")
                        logger.debug(f"이미지 추출: {filename}")

                    except Exception as e:
                        logger.warning(f"이미지 추출 실패 (page {page_num}, xref {xref}): {e}")

        finally:
            doc.close()

        markdown = "\n".join(markdown_parts)

        # 기본적인 Markdown 정리
        markdown = self._cleanup_markdown(markdown)

        logger.info(f"PDF 변환 완료: {len(assets)}개 이미지 추출")

        return ConversionResult(markdown=markdown, assets=assets, metadata=metadata)

    def _extract_metadata(self, doc) -> Metadata:
        """PDF 메타데이터 추출"""
        meta = doc.metadata or {}

        # 날짜 형식 변환 (D:20240101120000 -> 2024-01-01)
        def parse_pdf_date(date_str: str | None) -> str | None:
            if not date_str:
                return None
            # D:YYYYMMDDHHmmSS 형식
            if date_str.startswith("D:"):
                date_str = date_str[2:]
            if len(date_str) >= 8:
                return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
            return None

        return Metadata(
            title=meta.get("title") or None,
            author=meta.get("author") or None,
            created=parse_pdf_date(meta.get("creationDate")),
            modified=parse_pdf_date(meta.get("modDate")),
            pages=doc.page_count,
        )

    def _process_table(self, table) -> str:
        """PyMuPDF 테이블을 Markdown 테이블로 변환"""
        try:
            # 테이블 데이터 추출
            data = table.extract()
            if not data or not data[0]:
                return ""

            md_rows: list[str] = []
            for row in data:
                # 셀 텍스트 정리 (None 처리 및 줄바꿈 제거)
                cells = [
                    (cell or "").replace("\n", " ").strip()
                    for cell in row
                ]
                md_rows.append("| " + " | ".join(cells) + " |")

            if not md_rows:
                return ""

            # 헤더 구분선 추가
            col_count = len(data[0])
            separator = "| " + " | ".join(["---"] * col_count) + " |"
            md_rows.insert(1, separator)

            return "\n".join(md_rows) + "\n"
        except Exception as e:
            logger.debug(f"테이블 변환 실패: {e}")
            return ""

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
