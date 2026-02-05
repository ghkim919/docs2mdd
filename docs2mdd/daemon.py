"""데몬 프로세스 관리"""

import logging
import os
import signal
import sys
import time
from pathlib import Path

from .config import Config
from .watcher import FileWatcher

logger = logging.getLogger(__name__)


class Daemon:
    """docs2mdd 데몬 프로세스"""

    def __init__(self, config: Config):
        self.config = config
        self.watcher: FileWatcher | None = None
        self._running = False

    @property
    def pid_file(self) -> Path:
        return Path(self.config.daemon.pid_file)

    def start(self, foreground: bool = False) -> None:
        """데몬 시작"""
        if self._is_running():
            logger.error("데몬이 이미 실행 중입니다")
            sys.exit(1)

        if foreground:
            self._run()
        else:
            self._daemonize()

    def stop(self) -> None:
        """데몬 중지"""
        if not self.pid_file.exists():
            logger.error("PID 파일이 없습니다. 데몬이 실행 중이 아닌 것 같습니다")
            return

        pid = int(self.pid_file.read_text().strip())

        try:
            os.kill(pid, signal.SIGTERM)
            logger.info(f"데몬 종료 신호 전송 (PID: {pid})")

            # 종료 대기
            for _ in range(10):
                time.sleep(0.5)
                try:
                    os.kill(pid, 0)  # 프로세스 존재 확인
                except ProcessLookupError:
                    break
            else:
                logger.warning("데몬이 정상 종료되지 않아 강제 종료합니다")
                os.kill(pid, signal.SIGKILL)

        except ProcessLookupError:
            logger.warning("데몬 프로세스가 이미 종료되었습니다")

        finally:
            if self.pid_file.exists():
                self.pid_file.unlink()

        logger.info("데몬 종료 완료")

    def status(self) -> bool:
        """데몬 상태 확인"""
        if self._is_running():
            pid = int(self.pid_file.read_text().strip())
            logger.info(f"데몬 실행 중 (PID: {pid})")
            return True
        else:
            logger.info("데몬이 실행 중이 아닙니다")
            return False

    def _is_running(self) -> bool:
        """데몬이 실행 중인지 확인"""
        if not self.pid_file.exists():
            return False

        try:
            pid = int(self.pid_file.read_text().strip())
            os.kill(pid, 0)  # 프로세스 존재 확인
            return True
        except (ProcessLookupError, ValueError):
            # PID 파일은 있지만 프로세스가 없음
            self.pid_file.unlink()
            return False

    def _daemonize(self) -> None:
        """데몬화 (fork)"""
        # 첫 번째 fork
        try:
            pid = os.fork()
            if pid > 0:
                sys.exit(0)
        except OSError as e:
            logger.error(f"첫 번째 fork 실패: {e}")
            sys.exit(1)

        # 세션 리더가 됨
        os.setsid()

        # 두 번째 fork
        try:
            pid = os.fork()
            if pid > 0:
                sys.exit(0)
        except OSError as e:
            logger.error(f"두 번째 fork 실패: {e}")
            sys.exit(1)

        # 작업 디렉토리 변경
        os.chdir("/")

        # 파일 디스크립터 닫기
        sys.stdout.flush()
        sys.stderr.flush()

        with open("/dev/null", "r") as devnull:
            os.dup2(devnull.fileno(), sys.stdin.fileno())
        with open("/dev/null", "a+") as devnull:
            os.dup2(devnull.fileno(), sys.stdout.fileno())
            os.dup2(devnull.fileno(), sys.stderr.fileno())

        # PID 파일 생성
        self._write_pid()

        # 시그널 핸들러 설정
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

        self._run()

    def _run(self) -> None:
        """메인 실행 루프"""
        self._running = True

        # PID 파일 생성 (foreground 모드)
        if not self.pid_file.exists():
            self._write_pid()

        # 시그널 핸들러 설정
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

        logger.info("docs2mdd 데몬 시작")
        logger.info(f"소스 디렉토리: {self.config.src_dir}")
        logger.info(f"대상 디렉토리: {self.config.dest_dir}")

        self.watcher = FileWatcher(self.config)

        # 기존 파일 처리
        self.watcher.process_existing_files()

        # 감시 시작
        self.watcher.start()

        try:
            while self._running and self.watcher.is_alive():
                time.sleep(self.config.daemon.poll_interval)
        except Exception as e:
            logger.error(f"데몬 오류: {e}")
        finally:
            self._cleanup()

    def _write_pid(self) -> None:
        """PID 파일 생성"""
        self.pid_file.parent.mkdir(parents=True, exist_ok=True)
        self.pid_file.write_text(str(os.getpid()))

    def _handle_signal(self, signum: int, frame) -> None:
        """시그널 핸들러"""
        logger.info(f"시그널 수신: {signum}")
        self._running = False

    def _cleanup(self) -> None:
        """정리 작업"""
        if self.watcher:
            self.watcher.stop()

        if self.pid_file.exists():
            self.pid_file.unlink()

        logger.info("데몬 종료")
