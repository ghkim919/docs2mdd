"""HTML 변환기"""

import base64
import logging
import mimetypes
import re
import urllib.request
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag
from markdownify import MarkdownConverter

from .base import Asset, ConversionResult, Converter

logger = logging.getLogger(__name__)


class CustomMarkdownConverter(MarkdownConverter):
    """이미지 처리를 위한 커스텀 Markdown 변환기"""

    def __init__(self, **kwargs):
        self.image_handler = kwargs.pop("image_handler", None)
        super().__init__(**kwargs)

    def convert_img(self, el: Tag, text: str, parent_tags: set | None = None) -> str:
        """이미지 태그를 Markdown으로 변환"""
        src = el.get("src", "")
        alt = el.get("alt", "")

        if self.image_handler and src:
            new_src = self.image_handler(src)
            if new_src:
                src = new_src

        return f"![{alt}]({src})"


class HtmlConverter(Converter):
    """HTML을 Markdown으로 변환하는 변환기"""

    supported_extensions = [".html", ".htm"]

    # 이미지 다운로드 타임아웃 (초)
    IMAGE_TIMEOUT = 10

    def convert(self, file_path: Path) -> ConversionResult:
        """
        HTML 파일을 Markdown으로 변환

        Args:
            file_path: HTML 파일 경로

        Returns:
            ConversionResult: 변환된 Markdown과 추출된 이미지
        """
        logger.info(f"HTML 변환 시작: {file_path}")

        # HTML 파일 읽기
        html_content = file_path.read_text(encoding="utf-8", errors="ignore")

        # BeautifulSoup으로 파싱
        soup = BeautifulSoup(html_content, "html.parser")

        # 불필요한 요소 제거
        for tag in soup.find_all(["script", "style", "head", "meta", "link"]):
            tag.decompose()

        # 이미지 추출 및 처리
        assets: list[Asset] = []
        image_counter = 0
        image_map: dict[str, str] = {}  # 원본 src -> 새 경로 매핑

        for img in soup.find_all("img"):
            src = img.get("src", "")
            if not src:
                continue

            asset = self._process_image(src, file_path, image_counter)
            if asset:
                image_counter += 1
                assets.append(asset)
                image_map[src] = f"./assets/{asset.filename}"
                logger.debug(f"이미지 추출: {asset.filename}")

        # 이미지 핸들러 생성
        def image_handler(src: str) -> str | None:
            return image_map.get(src)

        # Markdown 변환
        converter = CustomMarkdownConverter(
            heading_style="atx",
            bullets="-",
            strip=["a"] if not soup.find("a") else [],
            image_handler=image_handler,
        )

        # body가 있으면 body만, 없으면 전체
        body = soup.find("body")
        content = body if body else soup

        markdown = converter.convert(str(content))
        markdown = self._cleanup_markdown(markdown)

        logger.info(f"HTML 변환 완료: {len(assets)}개 이미지 추출")

        return ConversionResult(markdown=markdown, assets=assets)

    def _process_image(
        self, src: str, html_path: Path, counter: int
    ) -> Asset | None:
        """이미지 소스를 처리하여 Asset 생성"""
        try:
            # Data URI 처리 (base64 인코딩된 이미지)
            if src.startswith("data:"):
                return self._process_data_uri(src, counter)

            # 절대 URL 처리
            parsed = urlparse(src)
            if parsed.scheme in ("http", "https"):
                return self._download_image(src, counter)

            # 상대 경로 처리
            image_path = html_path.parent / src
            if image_path.exists():
                return self._read_local_image(image_path, counter)

            logger.warning(f"이미지를 찾을 수 없음: {src}")
            return None

        except Exception as e:
            logger.warning(f"이미지 처리 실패: {src} - {e}")
            return None

    def _process_data_uri(self, data_uri: str, counter: int) -> Asset | None:
        """Data URI에서 이미지 추출"""
        # data:image/png;base64,iVBORw0... 형식 파싱
        match = re.match(r"data:image/(\w+);base64,(.+)", data_uri)
        if not match:
            return None

        ext = match.group(1)
        if ext == "jpeg":
            ext = "jpg"

        data = base64.b64decode(match.group(2))
        filename = f"img_{counter + 1:03d}.{ext}"

        return Asset(
            filename=filename,
            data=data,
            mime_type=f"image/{ext}",
        )

    def _download_image(self, url: str, counter: int) -> Asset | None:
        """URL에서 이미지 다운로드"""
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 docs2mdd/0.1.0"},
            )
            with urllib.request.urlopen(req, timeout=self.IMAGE_TIMEOUT) as response:
                data = response.read()
                content_type = response.headers.get("Content-Type", "image/png")

                # 확장자 추출
                ext = content_type.split("/")[-1].split(";")[0]
                if ext == "jpeg":
                    ext = "jpg"
                elif ext not in ("png", "jpg", "gif", "webp", "svg+xml"):
                    # URL에서 확장자 추출 시도
                    path = urlparse(url).path
                    ext = Path(path).suffix.lstrip(".") or "png"

                if ext == "svg+xml":
                    ext = "svg"

                filename = f"img_{counter + 1:03d}.{ext}"

                return Asset(
                    filename=filename,
                    data=data,
                    mime_type=content_type,
                )
        except Exception as e:
            logger.warning(f"이미지 다운로드 실패: {url} - {e}")
            return None

    def _read_local_image(self, image_path: Path, counter: int) -> Asset | None:
        """로컬 이미지 파일 읽기"""
        data = image_path.read_bytes()
        ext = image_path.suffix.lstrip(".").lower()
        if ext == "jpeg":
            ext = "jpg"

        mime_type, _ = mimetypes.guess_type(str(image_path))
        if not mime_type:
            mime_type = f"image/{ext}"

        filename = f"img_{counter + 1:03d}.{ext}"

        return Asset(
            filename=filename,
            data=data,
            mime_type=mime_type,
        )

    def _cleanup_markdown(self, text: str) -> str:
        """Markdown 텍스트 정리"""
        # 연속된 빈 줄 정리
        text = re.sub(r"\n{3,}", "\n\n", text)

        # 앞뒤 공백 제거
        text = text.strip()

        return text
