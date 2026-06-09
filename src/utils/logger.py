"""
日誌設定 — 使用 loguru
"""
import sys

from loguru import logger


def setup_logger(log_level: str = "INFO") -> None:
    """設定全域 logger"""
    logger.remove()  # 移除預設 handler

    # 終端機輸出（彩色）
    logger.add(
        sys.stderr,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan> | "
            "<level>{message}</level>"
        ),
        level=log_level,
        colorize=True,
    )

    # 檔案輸出（輪替）
    logger.add(
        "logs/stockaa_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function} | {message}",
        level="DEBUG",
        rotation="1 day",
        retention="7 days",
        encoding="utf-8",
    )


__all__ = ["logger", "setup_logger"]
