"""
Тест для проверки работы сканирования с .gitignore
"""

import asyncio
import tempfile
from pathlib import Path
from ingestor.app.pipeline.scan import ScanStage


async def test_gitignore_scan():
    """
    Создаёт временную директорию с файлами и .gitignore,
    проверяет правильность фильтрации.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        
        # Создаём структуру файлов
        (workspace / "file1.py").write_text("print('hello')")
        (workspace / "file2.txt").write_text("some text")
        (workspace / "README.md").write_text("# README")
        
        # Создаём поддиректорию
        subdir = workspace / "subdir"
        subdir.mkdir()
        (subdir / "file3.py").write_text("print('world')")
        (subdir / "ignored.log").write_text("log data")
        
        # Создаём директорию для игнорирования
        ignored_dir = workspace / "ignored_dir"
        ignored_dir.mkdir()
        (ignored_dir / "should_not_appear.py").write_text("ignored")
        
        # Создаём бинарный файл
        (workspace / "binary.bin").write_bytes(b'\x00\x01\x02\x03')
        
        # Создаём .gitignore в корне
        gitignore_content = """
# Игнорируем логи
*.log

# Игнорируем директорию
ignored_dir/

# Игнорируем бинарные файлы
*.bin
"""
        (workspace / ".gitignore").write_text(gitignore_content)
        
        # Создаём .gitignore в поддиректории
        (subdir / ".gitignore").write_text("# Дополнительные правила\n*.tmp\n")
        (subdir / "temp.tmp").write_text("temporary")
        
        # Запускаем сканирование
        scanner = ScanStage(str(workspace))
        files = await scanner.run()
        
        # Проверяем результаты
        file_paths = {f.relative_path for f in files}
        
        print(f"\n✓ Найдено файлов: {len(files)}")
        print(f"✓ Список файлов:")
        for f in sorted(file_paths):
            print(f"  - {f}")
        
        # Проверки
        assert "file1.py" in file_paths, "file1.py должен быть найден"
        assert "file2.txt" in file_paths, "file2.txt должен быть найден"
        assert "README.md" in file_paths, "README.md должен быть найден"
        assert str(Path("subdir") / "file3.py") in file_paths, "subdir/file3.py должен быть найден"
        
        # Проверяем, что игнорируемые файлы НЕ найдены
        assert str(Path("subdir") / "ignored.log") not in file_paths, "subdir/ignored.log должен быть проигнорирован"
        assert str(Path("ignored_dir") / "should_not_appear.py") not in file_paths, "ignored_dir/should_not_appear.py должен быть проигнорирован"
        assert "binary.bin" not in file_paths, "binary.bin должен быть проигнорирован (бинарный)"
        assert str(Path("subdir") / "temp.tmp") not in file_paths, "subdir/temp.tmp должен быть проигнорирован (по .gitignore в subdir)"
        
        print("\n✅ Все проверки пройдены!")
        print(f"✅ .gitignore фильтрация работает корректно")
        print(f"✅ Бинарные файлы отфильтрованы")
        print(f"✅ Поддержка вложенных .gitignore работает")


if __name__ == "__main__":
    asyncio.run(test_gitignore_scan())
