import asyncio
import os
from pathlib import Path


async def test_scan():
    workspace = Path("/workspace")

    def get_files():
        files = []
        for root, dirs, filenames in os.walk(workspace):
            # Простейшая фильтрация
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('__pycache__', 'node_modules')]
            for f in filenames:
                files.append(Path(root) / f)
                if len(files) >= 100:  # Лимит для теста
                    return files
        return files

    loop = asyncio.get_event_loop()
    files = await loop.run_in_executor(None, get_files)
    print(f"Found {len(files)} files")
    return files


# Тест
asyncio.run(test_scan())
