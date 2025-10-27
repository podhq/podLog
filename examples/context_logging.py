"""Minimal example demonstrating podlog context logging."""

from __future__ import annotations

import time

import podlog


def main() -> None:
    podlog.configure(
        {
            "paths": {"base_dir": "example-logs", "date_folder_mode": "flat"},
            "formatters": {"text": {"demo": {"show_extras": True}}},
            "handlers": {
                "enabled": ["file"],
                "file": {
                    "type": "file",
                    "filename": "example.log",
                    "formatter": "text.demo",
                    "level": "INFO",
                },
            },
            "logging": {"root": {"level": "INFO", "handlers": ["file"]}},
        }
    )

    logger = podlog.get_context_logger("examples.orders", app="podlog-demo", env="dev")
    for order_id in range(1, 4):
        logger.add_extra(order_id=order_id, total=order_id * 19.99)
        logger.info("processed order")
        time.sleep(0.1)


if __name__ == "__main__":
    main()
