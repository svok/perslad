#!/usr/bin/env python3
import os
import sys
from pathlib import Path

import pandas as pd
from phoenix.client import Client


class DatasetLoader:
    def __init__(self, phoenix_endpoint: str):
        self._client = Client(base_url=phoenix_endpoint)

    def load_dataset_from_csv(
            self,
            csv_path: str,
            dataset_name: str,
            input_keys: list,
            output_keys: list,
            metadata_keys: list = None,
    ):
        """
        Загружает CSV-файл как датасет в Phoenix.

        :param csv_path: путь к CSV-файлу
        :param dataset_name: имя датасета в Phoenix
        :param input_keys: список колонок, используемых как входные данные
        :param output_keys: список колонок, используемых как ожидаемый вывод
        :param metadata_keys: список колонок для дополнительной метаинформации (опционально)
        """
        if not Path(csv_path).exists():
            print(f"❌ Файл {csv_path} не найден")
            sys.exit(1)

        df = pd.read_csv(csv_path)
        # Заменяем NaN на None, чтобы избежать проблем с JSON
        df = df.where(pd.notnull(df), None)
        print(f"📁 Загрузка {len(df)} строк из {csv_path}")

        # Проверяем, что все указанные колонки существуют в DataFrame
        all_keys = input_keys + output_keys + (metadata_keys or [])
        missing = [col for col in all_keys if col not in df.columns]
        if missing:
            print(f"❌ В CSV отсутствуют колонки: {missing}")
            sys.exit(1)

        # Создаём датасет
        try:
            dataset = self._client.datasets.create_dataset(
                dataframe=df,
                name=dataset_name,
                input_keys=input_keys,
                output_keys=output_keys,
                metadata_keys=metadata_keys,
            )
            print(f"✅ Датасет '{dataset_name}' успешно создан (ID: {dataset.id})")
            print(f"   Версия: {dataset.version_id}, примеров: {len(dataset)}")
        except Exception as e:
            print(f"❌ Ошибка при создании датасета: {e}")
            sys.exit(1)


def main():
    # Параметры можно задавать через переменные окружения
    csv_path = os.getenv("DATASET_PATH", "./evaluations.csv")
    phoenix_endpoint = os.getenv("PHOENIX_ENDPOINT", "http://localhost:6006")
    dataset_name = os.getenv("DATASET_NAME", "my-dataset")

    # Укажите здесь, какие колонки в CSV являются входом, выходом и метаданными
    # Пример: input_keys = ["query"], output_keys = ["response"], metadata_keys = ["category"]
    input_keys = os.getenv("INPUT_KEYS", "input").split(",")  # ожидается "col1,col2"
    output_keys = os.getenv("OUTPUT_KEYS", "output").split(",")
    metadata_keys = os.getenv("METADATA_KEYS", "").split(",") if os.getenv("METADATA_KEYS") else None

    loader = DatasetLoader(phoenix_endpoint)
    loader.load_dataset_from_csv(
        csv_path=csv_path,
        dataset_name=dataset_name,
        input_keys=input_keys,
        output_keys=output_keys,
        metadata_keys=metadata_keys,
    )


if __name__ == "__main__":
    main()
