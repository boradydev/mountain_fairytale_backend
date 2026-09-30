from pathlib import Path


def sql_reader(
    filename: str,
    module_path: str,
) -> str:
    """
    Получает SQL скрипт из файла.

    Args:
        filename: Имя SQL скрипта
        module_path: Путь до текущего модуля обычно __file__
    Returns:
        Текст из SQL скрипта
    """
    current_script_dir = Path(module_path).resolve().parent
    sql_path = current_script_dir / filename
    return sql_path.read_text(encoding="utf-8")
