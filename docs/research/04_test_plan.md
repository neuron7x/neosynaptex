# 04_test_plan

## Red → Green

1. Очікувано отримати FAIL для `check_six_file_presence.py`, якщо один з 6 файлів відсутній/порожній.
2. Додати/заповнити всі 6 файлів.
3. Повторний запуск має дати PASS.

## Contract coverage

- Перевірити, що JSON-аудити генеруються і містять `protocol_id`, `check_id`, `status`.

## Adversarial cases

- Порожній файл у six-file наборі.
- Неправильний шлях до артефакту.
