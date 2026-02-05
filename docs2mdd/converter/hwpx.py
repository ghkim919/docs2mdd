"""한글 (HWPX) 변환기"""

import logging
import mimetypes
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from .base import Asset, ConversionResult, Converter

logger = logging.getLogger(__name__)

# HWPX XML 네임스페이스
NAMESPACES = {
    "hp": "http://www.hancom.co.kr/hwpml/2011/paragraph",
    "hc": "http://www.hancom.co.kr/hwpml/2011/core",
    "para": "http://www.hancom.co.kr/hwpml/2011/paragraph",
    "text": "http://www.hancom.co.kr/hwpml/2011/text",
}


class HwpxConverter(Converter):
    """한글 HWPX 문서를 Markdown으로 변환하는 변환기"""

    supported_extensions = [".hwpx"]

    def convert(self, file_path: Path) -> ConversionResult:
        """
        HWPX 파일을 Markdown으로 변환

        Args:
            file_path: HWPX 파일 경로

        Returns:
            ConversionResult: 변환된 Markdown과 추출된 이미지
        """
        logger.info(f"HWPX 변환 시작: {file_path}")

        markdown_parts: list[str] = []
        assets: list[Asset] = []
        image_counter = 0

        with zipfile.ZipFile(file_path, "r") as zf:
            # 이미지 맵 생성 (BinData 폴더의 파일들)
            image_map = self._extract_images(zf)

            # 섹션 파일들 찾기 (section0.xml, section1.xml, ...)
            section_files = sorted(
                [name for name in zf.namelist() if self._is_section_file(name)]
            )

            if not section_files:
                logger.warning(f"섹션 파일을 찾을 수 없음: {file_path}")
                return ConversionResult(markdown="", assets=[])

            # 각 섹션 처리
            for section_file in section_files:
                section_xml = zf.read(section_file).decode("utf-8")
                section_md, section_assets, image_counter = self._process_section(
                    section_xml, image_map, image_counter
                )
                markdown_parts.extend(section_md)
                assets.extend(section_assets)

        markdown = "\n\n".join(markdown_parts)
        markdown = self._cleanup_markdown(markdown)

        logger.info(f"HWPX 변환 완료: {len(assets)}개 이미지 추출")

        return ConversionResult(markdown=markdown, assets=assets)

    def _is_section_file(self, name: str) -> bool:
        """섹션 파일인지 확인"""
        # Contents/section0.xml, Contents/section1.xml 등
        return (
            name.startswith("Contents/section")
            and name.endswith(".xml")
        )

    def _extract_images(self, zf: zipfile.ZipFile) -> dict[str, tuple[bytes, str]]:
        """BinData 폴더에서 이미지 추출"""
        image_map: dict[str, tuple[bytes, str]] = {}

        for name in zf.namelist():
            if name.startswith("BinData/"):
                filename = name.split("/")[-1]
                if not filename:
                    continue

                try:
                    data = zf.read(name)
                    # 확장자 추출
                    ext = Path(filename).suffix.lower().lstrip(".")
                    if not ext:
                        # MIME 타입 추측
                        mime_type, _ = mimetypes.guess_type(filename)
                        if mime_type and mime_type.startswith("image/"):
                            ext = mime_type.split("/")[-1]
                        else:
                            ext = "bin"

                    if ext == "jpeg":
                        ext = "jpg"

                    image_map[filename] = (data, ext)
                    logger.debug(f"이미지 추출: {filename}")
                except Exception as e:
                    logger.warning(f"이미지 추출 실패: {name} - {e}")

        return image_map

    def _process_section(
        self,
        section_xml: str,
        image_map: dict[str, tuple[bytes, str]],
        image_counter: int,
    ) -> tuple[list[str], list[Asset], int]:
        """섹션 XML을 파싱하여 Markdown으로 변환"""
        markdown_parts: list[str] = []
        assets: list[Asset] = []

        try:
            root = ET.fromstring(section_xml)
        except ET.ParseError as e:
            logger.error(f"XML 파싱 오류: {e}")
            return [], [], image_counter

        # 처리된 요소들 추적 (테이블 내부 요소 중복 방지)
        processed_elements: set[int] = set()
        # 처리된 이미지 추적 (중복 방지)
        processed_images: set[str] = set()

        # 모든 요소 순회
        for elem in root.iter():
            elem_id = id(elem)

            # 이미 처리된 요소는 건너뛰기
            if elem_id in processed_elements:
                continue

            # 테이블 요소 처리 (테이블 먼저 처리하고 내부 요소 마킹)
            if elem.tag.endswith("}tbl") or elem.tag == "tbl":
                table_md = self._process_table(elem)
                if table_md:
                    markdown_parts.append(table_md)
                # 테이블 내부 모든 요소를 처리됨으로 표시
                for child in elem.iter():
                    processed_elements.add(id(child))

            # 단락 요소 처리
            elif elem.tag.endswith("}p") or elem.tag == "p":
                para_md, para_assets, image_counter = self._process_paragraph(
                    elem, image_map, image_counter
                )
                if para_md:
                    markdown_parts.append(para_md)
                    assets.extend(para_assets)
                    for asset in para_assets:
                        processed_images.add(asset.filename)

            # 독립 이미지(pic) 요소 처리 (단락 외부에 있는 경우)
            elif elem.tag.endswith("}pic") or elem.tag == "pic":
                img_md, img_asset, image_counter = self._process_image(
                    elem, image_map, image_counter
                )
                if img_asset and img_asset.filename not in processed_images:
                    markdown_parts.append(img_md)
                    assets.append(img_asset)
                    processed_images.add(img_asset.filename)

        return markdown_parts, assets, image_counter

    def _process_paragraph(
        self,
        para: ET.Element,
        image_map: dict[str, tuple[bytes, str]],
        image_counter: int,
    ) -> tuple[str, list[Asset], int]:
        """단락 요소를 Markdown으로 변환"""
        assets: list[Asset] = []
        text_parts: list[str] = []

        # 모든 텍스트(t) 요소 수집
        for elem in para.iter():
            if elem.tag.endswith("}t") or elem.tag == "t":
                if elem.text:
                    text_parts.append(elem.text)

            # 이미지(pic) 요소 처리
            elif elem.tag.endswith("}pic") or elem.tag == "pic":
                img_md, img_asset, image_counter = self._process_image(
                    elem, image_map, image_counter
                )
                if img_md:
                    text_parts.append(img_md)
                if img_asset:
                    assets.append(img_asset)

        text = "".join(text_parts).strip()

        # 스타일 확인 (outline level로 헤딩 판단)
        outline_level = self._get_outline_level(para)
        if outline_level and text:
            level = min(outline_level, 6)
            text = "#" * level + " " + text

        return text, assets, image_counter

    def _get_outline_level(self, para: ET.Element) -> int | None:
        """단락의 아웃라인 레벨 확인 (헤딩용)"""
        # paraHead 요소에서 outlineLevel 속성 확인
        for elem in para.iter():
            if elem.tag.endswith("}paraHead") or elem.tag == "paraHead":
                outline = elem.get("outlineLevel")
                if outline:
                    try:
                        return int(outline)
                    except ValueError:
                        pass
        return None

    def _process_image(
        self,
        pic_elem: ET.Element,
        image_map: dict[str, tuple[bytes, str]],
        image_counter: int,
    ) -> tuple[str, Asset | None, int]:
        """이미지 요소를 처리하여 Asset 생성"""
        bin_ref = None

        # 방법 1: binItem 요소에서 참조 파일명 찾기
        for elem in pic_elem.iter():
            if elem.tag.endswith("}binItem") or elem.tag == "binItem":
                bin_ref = (
                    elem.get("src")
                    or elem.get("href")
                    or elem.get("{http://www.w3.org/1999/xlink}href")
                )
                if not bin_ref:
                    bin_id = elem.get("id") or elem.get("binaryItemIDRef")
                    if bin_id:
                        for filename in image_map:
                            if filename.startswith(bin_id) or bin_id in filename:
                                bin_ref = filename
                                break
                if bin_ref:
                    break

        # 방법 2: imageRect 또는 img 요소에서 찾기
        if not bin_ref:
            for elem in pic_elem.iter():
                if elem.tag.endswith("}imageRect") or elem.tag == "imageRect":
                    bin_ref = elem.get("binaryItemIDRef")
                    if bin_ref:
                        for filename in image_map:
                            if filename.startswith(bin_ref) or bin_ref in filename:
                                bin_ref = filename
                                break
                        break

        # 방법 3: pic 요소 자체의 속성 확인
        if not bin_ref:
            for attr in ["binaryItemIDRef", "id", "itemId"]:
                ref_id = pic_elem.get(attr)
                if ref_id:
                    for filename in image_map:
                        if filename.startswith(ref_id) or ref_id in filename:
                            bin_ref = filename
                            break
                if bin_ref:
                    break

        # 방법 4: shapeComponent에서 찾기
        if not bin_ref:
            for elem in pic_elem.iter():
                if "shapeComponent" in elem.tag or "ShapeComponent" in elem.tag:
                    ref_id = elem.get("binaryItemIDRef") or elem.get("href")
                    if ref_id:
                        for filename in image_map:
                            if filename.startswith(ref_id) or ref_id in filename:
                                bin_ref = filename
                                break
                if bin_ref:
                    break

        if not bin_ref:
            logger.debug(f"이미지 참조를 찾을 수 없음: {ET.tostring(pic_elem, encoding='unicode')[:200]}")
            return "", None, image_counter

        # 파일명만 추출
        ref_filename = bin_ref.split("/")[-1]

        if ref_filename not in image_map:
            logger.warning(f"이미지 파일을 찾을 수 없음: {ref_filename}")
            return "", None, image_counter

        image_data, ext = image_map[ref_filename]
        image_counter += 1
        new_filename = f"img_{image_counter:03d}.{ext}"

        asset = Asset(
            filename=new_filename,
            data=image_data,
            mime_type=f"image/{ext}",
        )

        md_text = f"\n\n![Image {image_counter}](./assets/{new_filename})"
        logger.debug(f"이미지 변환: {ref_filename} -> {new_filename}")

        return md_text, asset, image_counter

    def _process_table(self, tbl_elem: ET.Element) -> str:
        """테이블 요소를 Markdown 테이블로 변환"""
        rows: list[list[str]] = []

        # 행(tr) 요소 찾기
        for row_elem in tbl_elem.iter():
            if row_elem.tag.endswith("}tr") or row_elem.tag == "tr":
                cells: list[str] = []

                # 셀(tc) 요소 찾기
                for cell_elem in row_elem.iter():
                    if cell_elem.tag.endswith("}tc") or cell_elem.tag == "tc":
                        cell_text = self._extract_cell_text(cell_elem)
                        cells.append(cell_text)

                if cells:
                    rows.append(cells)

        if not rows:
            return ""

        # Markdown 테이블 생성
        md_rows: list[str] = []
        for row in rows:
            md_rows.append("| " + " | ".join(row) + " |")

        # 헤더 구분선 추가
        if md_rows:
            col_count = len(rows[0]) if rows else 0
            separator = "| " + " | ".join(["---"] * col_count) + " |"
            md_rows.insert(1, separator)

        return "\n".join(md_rows)

    def _extract_cell_text(self, cell_elem: ET.Element) -> str:
        """셀 요소에서 텍스트 추출"""
        text_parts: list[str] = []

        for elem in cell_elem.iter():
            if elem.tag.endswith("}t") or elem.tag == "t":
                if elem.text:
                    text_parts.append(elem.text)

        return " ".join(text_parts).replace("\n", " ").strip()

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
