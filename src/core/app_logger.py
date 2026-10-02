import logging

def logger_config() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s:     %(message)s     %(name)s"
    )