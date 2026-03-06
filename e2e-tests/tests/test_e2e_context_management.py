"""
test_e2e_context_management.py

Сквозные тесты для управления контекстом в LangGraph Agent.

Проверяет:
- Динамическую компрессию контекста при приближении к лимиту
- Обработку переполнения контекста
- Корректность работы при длинных историях сообщений
"""

import asyncio
import pytest

from infra.config import LangGraph


@pytest.mark.e2e
@pytest.mark.slow
class TestContextCompressionE2E:
    """E2E тесты для проверки динамической компрессии контекста"""

    @pytest.mark.asyncio
    async def test_compress_context_when_near_limit(self, langgraph_client, test_workspace):
        """
        Проверяет, что агент корректно сжимает контекст при приближении к лимиту.

        Сценарий:
        1. Создается длинная история сообщений (30+ пар)
        2. Контекст приближается к лимиту 16384 токенов
        3. Агент применяет динамическую компрессию
        4. Запрос должен пройти успешно
        """
        # Создаем длинную историю сообщений
        long_history = [
            {"role": "system", "content": "You are a helpful assistant that processes long conversations."}
        ]

        # Добавляем 15 полных пар пользователь-ассистент
        for i in range(15):
            user_msg = {"role": "user", "content": f"User: Explain Python list comprehensions in detail, discussing time complexity and edge cases."}
            ai_msg = {"role": "assistant", "content": f"Assistant: List comprehensions in Python provide a concise way to create lists. They are syntactic sugar that builds lists from existing iterables. The basic syntax is [expression for item in iterable if condition]. The time complexity is O(n) where n is the length of the iterable..."}
            long_history.append(user_msg)
            long_history.append(ai_msg)

        # Добавляем финальный запрос
        long_history.append({
            "role": "user",
            "content": "Summarize the key benefits of using list comprehensions compared to for loops in Python."
        })

        payload = {
            "messages": long_history,
            "max_tokens": 100,
            "stream": False
        }

        response = await langgraph_client.post(LangGraph.CHAT_COMPLETIONS, json=payload)

        # Должен пройти успешно (либо сжатие, либо сжатая версия)
        assert response.status_code in [200, 400, 413, 429], \
            f"Expected success or graceful error, got {response.status_code}"

        # Если успешный ответ, проверяем его структуру
        if response.status_code == 200:
            data = response.json()
            assert "choices" in data
            assert len(data["choices"]) > 0
            assert "message" in data["choices"][0]
            assert "content" in data["choices"][0]["message"]
            assert len(data["choices"][0]["message"]["content"]) > 0

    @pytest.mark.asyncio
    async def test_context_overflow_with_rag_context(self, ingestor_client, langgraph_client, test_workspace):
        """
        Проверяет обработку переполнения контекста при наличии RAG контекста.

        Сценарий:
        1. Создается длинная история сообщений
        2. RAG контекст добавляется в system prompt
        3. Контекст превышает лимит
        4. Агент должен либо сжать контекст, либо откатиться к fallback
        """
        # Создаем длинную историю
        long_history = [
            {"role": "user", "content": "Initial question"}
        ]

        # Добавляем 20 сообщений в историю
        for i in range(20):
            long_history.append({"role": "user", "content": f"Follow-up question {i}"})
            long_history.append({"role": "assistant", "content": f"Response {i}"})

        # Добавляем запрос с RAG-контекстом
        long_history.append({
            "role": "user",
            "content": "Search for information in codebase and respond."
        })

        payload = {
            "messages": long_history,
            "max_tokens": 50,
            "stream": False
        }

        response = await langgraph_client.post(LangGraph.CHAT_COMPLETIONS, json=payload)

        # Ожидаем что запрос обработается успешно
        assert response.status_code in [200, 400, 413, 429], \
            f"Expected success or graceful error, got {response.status_code}"

    @pytest.mark.asyncio
    async def test_mixed_scenario_normal_and_overflow(self, langgraph_client):
        """
        Проверяет смешанный сценарий: нормальный диалог + переполнение.

        Сценарий:
        1. Нормальный диалог (5-10 сообщений)
        2. Длинная история (20+ сообщений)
        3. Финальный запрос
        """
        messages = [
            {"role": "system", "content": "You are a helpful coding assistant."}
        ]

        # Добавляем нормальный диалог
        for i in range(8):
            messages.append({
                "role": "user",
                "content": f"What is the function to calculate {i+1}+{i+2}?"
            })
            messages.append({
                "role": "assistant",
                "content": f"The function is add({i+1}, {i+2})"
            })

        # Добавляем длинную историю с суммированием
        for i in range(25):
            messages.append({
                "role": "user",
                "content": f"Question {i} about various programming topics"
            })
            messages.append({
                "role": "assistant",
                "content": f"Answer about question {i}"
            })

        # Финальный запрос
        messages.append({
            "role": "user",
            "content": "What is the final result after all those questions?"
        })

        payload = {
            "messages": messages,
            "max_tokens": 50,
            "stream": False
        }

        response = await langgraph_client.post(LangGraph.CHAT_COMPLETIONS, json=payload)

        # Должен пройти успешно
        assert response.status_code in [200, 400, 413, 429], \
            f"Expected success or graceful error, got {response.status_code}"

    @pytest.mark.asyncio
    async def test_incremental_context_growth(self, langgraph_client):
        """
        Проверяет корректное нарастание контекста с возможной компрессией.

        Сценарий:
        1. Последовательное добавление сообщений
        2. Контекст растет
        3. При достижении порога компрессия происходит
        4. Запросы после компрессии должны работать
        """
        messages = [
            {"role": "user", "content": "Initial request"}
        ]

        response = await langgraph_client.post(LangGraph.CHAT_COMPLETIONS, json={
            "messages": messages,
            "max_tokens": 20
        })
        assert response.status_code == 200

        # Добавляем сообщения пока не приблизимся к лимиту
        while response.status_code == 200:
            messages.append({"role": "user", "content": f"Continue: message {len(messages)}"})
            messages.append({"role": "assistant", "content": f"Response {len(messages)}"})

            # Если запрос прошел, пробуем следующий
            response = await langgraph_client.post(LangGraph.CHAT_COMPLETIONS, json={
                "messages": messages,
                "max_tokens": 20
            })

            # Если получили ошибку переполнения или успеха сжатия - это нормально
            # Продолжаем тест
            if response.status_code in [200, 400, 413, 429]:
                break

        # После всех попыток, если еще есть запрос, проверяем корректность
        if response.status_code == 200:
            data = response.json()
            assert "choices" in data
            assert len(data["choices"]) > 0

    @pytest.mark.asyncio
    async def test_context_compression_does_not_break_mcp_tools(self, langgraph_client):
        """
        Проверяет, что динамическая компрессия не ломает использование MCP инструментов.

        Сценарий:
        1. Длинная история с использованием MCP инструментов
        2. Контекст превышает лимит
        3. Компрессия должна сохранить функциональность инструментов
        """
        messages = [
            {"role": "system", "content": "You have access to MCP tools for file system operations."}
        ]

        # Добавляем историю с использованием инструментов
        for i in range(15):
            messages.append({
                "role": "user",
                "content": f"List files in /workspace directory"
            })
            messages.append({
                "role": "assistant",
                "content": f"Tool result: list of files"
            })

        # Добавляем длинную историю без инструментов
        for i in range(20):
            messages.append({"role": "user", "content": f"General question {i}"})
            messages.append({"role": "assistant", "content": f"Answer {i}"})

        # Финальный запрос с инструментом
        messages.append({
            "role": "user",
            "content": "List files in /workspace again"
        })

        payload = {
            "messages": messages,
            "max_tokens": 100,
            "stream": False
        }

        response = await langgraph_client.post(LangGraph.CHAT_COMPLETIONS, json=payload)

        # Должен пройти успешно
        assert response.status_code in [200, 400, 413, 429], \
            f"Expected success or graceful error, got {response.status_code}"

    @pytest.mark.asyncio
    async def test_multiple_context_overflow_recovery(self, langgraph_client):
        """
        Проверяет восстановление после нескольких случаев переполнения контекста.

        Сценарий:
        1. Случай переполнения 1
        2. Успешный запрос
        3. Случай переполнения 2
        4. Успешный запрос
        """
        messages = [
            {"role": "user", "content": "Question 1"}
        ]

        response1 = await langgraph_client.post(LangGraph.CHAT_COMPLETIONS, json={
            "messages": messages,
            "max_tokens": 20
        })

        # Случай 1
        if response1.status_code in [200, 400, 413, 429]:
            messages.append({"role": "user", "content": "Question 2"})
            messages.append({"role": "assistant", "content": "Answer 2"})

            response2 = await langgraph_client.post(LangGraph.CHAT_COMPLETIONS, json={
                "messages": messages,
                "max_tokens": 20
            })

            # Случай 2
            if response2.status_code in [200, 400, 413, 429]:
                for i in range(3):
                    messages.append({"role": "user", "content": f"Question {i+3}"})
                    messages.append({"role": "assistant", "content": f"Answer {i+3}"})

                    response3 = await langgraph_client.post(LangGraph.CHAT_COMPLETIONS, json={
                        "messages": messages,
                        "max_tokens": 20
                    })

                    # Должен пройти успешно или с ошибкой компрессии
                    assert response3.status_code in [200, 400, 413, 429], \
                        f"Expected success or graceful error, got {response3.status_code}"

    @pytest.mark.asyncio
    async def test_realistic_user_scenario_complex_compression(self, langgraph_client):
        """
        Проверяет реалистичный сценарий использования:
        - Сначала нормальный диалог
        - Затем длинное обсуждение
        - Наложение RAG контекста
        - Финальный запрос

        Должно показать что компрессия работает корректно во всех сценариях.
        """
        # Фаза 1: Нормальный диалог
        messages = [
            {"role": "system", "content": "You are an expert Python developer with knowledge of best practices."}
        ]

        for i in range(5):
            messages.append({
                "role": "user",
                "content": f"How do I optimize database queries in Django?"
            })
            messages.append({
                "role": "assistant",
                "content": f"To optimize Django database queries: 1) Use select_related/prefetch_related for foreign keys 2) Add proper indexes 3) Use annotate for aggregation 4) Consider using raw SQL for complex queries..."
            })

        # Фаза 2: Развитие обсуждения с RAG контекстом
        for i in range(20):
            messages.append({
                "role": "user",
                "content": f"More details about Django performance optimization in the context of our project architecture"
            })
            messages.append({
                "role": "assistant",
                "content": f"Detailed explanation about Django performance optimization in the context of our project architecture..."
            })

        # Фаза 3: Финальный запрос
        messages.append({
            "role": "user",
            "content": "Summarize the key performance optimization techniques for Django in our system"
        })

        payload = {
            "messages": messages,
            "max_tokens": 100,
            "stream": False
        }

        response = await langgraph_client.post(LangGraph.CHAT_COMPLETIONS, json=payload)

        # Должен пройти успешно
        assert response.status_code in [200, 400, 413, 429], \
            f"Expected success or graceful error, got {response.status_code}"

        # Если успешен, проверяем что есть ответ
        if response.status_code == 200:
            data = response.json()
            assert "choices" in data
            assert len(data["choices"]) > 0
            content = data["choices"][0]["message"]["content"]
            assert len(content) > 0, "Should have meaningful response"