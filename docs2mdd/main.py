"""CLI 엔트리포인트"""

import logging
from pathlib import Path

import click

from .config import Config
from .daemon import Daemon

logger = logging.getLogger(__name__)


@click.group()
@click.option(
    "-c", "--config",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="설정 파일 경로 (기본: ./config.yaml)",
)
@click.pass_context
def cli(ctx: click.Context, config: Path | None) -> None:
    """docs2mdd - 문서를 Markdown으로 자동 변환하는 데몬"""
    ctx.ensure_object(dict)

    # 설정 로드
    if config:
        ctx.obj["config"] = Config.from_file(config)
    elif Path("config.yaml").exists():
        ctx.obj["config"] = Config.from_file(Path("config.yaml"))
    else:
        ctx.obj["config"] = Config.default()

    # 로깅 설정
    ctx.obj["config"].setup_logging()


@cli.command()
@click.option(
    "-f", "--foreground",
    is_flag=True,
    help="포그라운드에서 실행 (디버깅용)",
)
@click.pass_context
def start(ctx: click.Context, foreground: bool) -> None:
    """데몬 시작"""
    config: Config = ctx.obj["config"]
    daemon = Daemon(config)

    if foreground:
        click.echo("포그라운드 모드로 시작합니다. Ctrl+C로 종료하세요.")
    else:
        click.echo("데몬을 시작합니다...")

    daemon.start(foreground=foreground)


@cli.command()
@click.pass_context
def stop(ctx: click.Context) -> None:
    """데몬 중지"""
    config: Config = ctx.obj["config"]
    daemon = Daemon(config)
    daemon.stop()


@cli.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """데몬 상태 확인"""
    config: Config = ctx.obj["config"]
    daemon = Daemon(config)

    if daemon.status():
        ctx.exit(0)
    else:
        ctx.exit(1)


@cli.command()
@click.pass_context
def restart(ctx: click.Context) -> None:
    """데몬 재시작"""
    config: Config = ctx.obj["config"]
    daemon = Daemon(config)

    click.echo("데몬 재시작 중...")
    daemon.stop()
    daemon.start(foreground=False)


@cli.command()
@click.argument("file_path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "-o", "--output",
    type=click.Path(path_type=Path),
    default=None,
    help="출력 디렉토리 (기본: 현재 디렉토리)",
)
@click.pass_context
def convert(ctx: click.Context, file_path: Path, output: Path | None) -> None:
    """단일 파일 변환 (데몬 없이)"""
    from .converter import DocxConverter, HtmlConverter, HwpxConverter, PDFConverter

    config: Config = ctx.obj["config"]

    # 출력 디렉토리 결정
    if output is None:
        output = Path.cwd() / file_path.stem
    output.mkdir(parents=True, exist_ok=True)

    # 변환기 선택
    converters = [PDFConverter(), DocxConverter(), HwpxConverter(), HtmlConverter()]
    converter = None
    for c in converters:
        if c.can_handle(file_path):
            converter = c
            break

    if converter is None:
        click.echo(f"지원하지 않는 파일 형식: {file_path.suffix}", err=True)
        ctx.exit(1)

    click.echo(f"변환 중: {file_path}")

    result = converter.convert(file_path)

    # Markdown 저장
    md_path = output / f"{file_path.stem}.md"
    md_path.write_text(result.markdown, encoding="utf-8")
    click.echo(f"Markdown 저장: {md_path}")

    # 에셋 저장
    if result.has_assets:
        assets_dir = output / config.assets_dirname
        assets_dir.mkdir(exist_ok=True)

        for asset in result.assets:
            asset_path = assets_dir / asset.filename
            asset_path.write_bytes(asset.data)

        click.echo(f"에셋 {len(result.assets)}개 저장: {assets_dir}")

    click.echo("변환 완료!")


@cli.command()
@click.pass_context
def init(ctx: click.Context) -> None:
    """현재 디렉토리에 기본 설정 파일 생성"""
    config_path = Path("config.yaml")

    if config_path.exists():
        click.echo("config.yaml이 이미 존재합니다.", err=True)
        ctx.exit(1)

    default_config = """# docs2mdd 설정 파일

# 소스 디렉토리 (감시할 디렉토리)
src_dir: "./src"

# 목적지 디렉토리 (변환된 파일 저장 위치)
dest_dir: "./dest"

# 지원 확장자
supported_extensions:
  - ".pdf"
  - ".docx"
  - ".hwpx"
  - ".html"
  - ".htm"

# 에셋 디렉토리 이름
assets_dirname: "assets"

# 로깅 설정
logging:
  level: "INFO"
  file: null

# 데몬 설정
daemon:
  pid_file: "/tmp/docs2mdd.pid"
  poll_interval: 1.0
"""

    config_path.write_text(default_config, encoding="utf-8")
    click.echo("config.yaml 생성 완료!")

    # src, dest 디렉토리 생성
    Path("src").mkdir(exist_ok=True)
    Path("dest").mkdir(exist_ok=True)
    click.echo("src/, dest/ 디렉토리 생성 완료!")


if __name__ == "__main__":
    cli()
