# 01_problem

Проблема: у PR/CI потоці Neosynaptex контрактні вимоги часто декларуються текстом, але не мають обов’язкового executable-enforcement до початку імплементації.

## Falsification Condition

Гіпотеза спростована, якщо PR проходить CI без machine-readable підтвердження для BLOCKER-інваріантів (зокрема PRE-03, MATH-01, VAL-01).
