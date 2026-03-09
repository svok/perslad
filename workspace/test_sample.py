# sample_test.py
# Минимальная реализация DataLoader для подготовки датасета
# Этап 2.3: Создание датасета

import torch
from torch.utils.data import Dataset, DataLoader
from transformers import BertTokenizer

class RussianTextDataset(Dataset):
    """Базовый датасет для русских текстов"""

    def __init__(self, texts, tokenizer, max_length=512):
        self.texts = texts
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        text = self.texts[idx]
        encoded = self.tokenizer(
            text,
            truncation=True,
            padding='max_length',
            max_length=self.max_length,
            return_tensors='pt'
        )
        return {
            'input_ids': encoded['input_ids'].squeeze(0),
            'attention_mask': encoded['attention_mask'].squeeze(0),
            'labels': encoded['input_ids'].squeeze(0)  # для авто-регрессии
        }

# Пример использования
if __name__ == "__main__":
    # Пример данных (в реальности загружаются из файла)
    texts = [
        "Привет, мир!",
        "Это пример текста на русском языке",
        "Нейросеть обучается на больших данных"
    ]

    # Инициализация токенизатора
    tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')

    # Создание датасета
    dataset = RussianTextDataset(texts, tokenizer, max_length=128)

    # Создание DataLoader
    batch_size = 2
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    # Пример итерации
    for batch in dataloader:
        print(f"Batch: {batch['input_ids']}")
        print(f"Attention mask: {batch['attention_mask']}")
        print("-" * 40)
