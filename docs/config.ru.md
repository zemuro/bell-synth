# Описание конфигурации

Анализатор можно настраивать через INI-файл. Флаги командной строки всегда перекрывают значения из конфига, а значения конфига перекрывают встроенные умолчания.

## Где искать конфиг

Поиск ведётся в таком порядке:

1. Файл, указанный через `--config /path/to/file.ini`.
2. `analyze_bell.ini` в текущем рабочем каталоге.
3. `analyze_bell.ini` рядом со скриптом (встроенные значения по умолчанию).
4. Встроенные значения по умолчанию.

Если конфиг не найден, программа использует встроенные значения и продолжает работу.

## Секции

### `[analysis]`

Параметры спектрального анализа.

### `[visualization]`

Параметры спектрограммы и графика спектра.

### `[output]`

Параметры текстового вывода.

## Описание ключей

| Ключ | Секция | Тип | По умолчанию | Единицы | Описание |
|------|--------|-----|--------------|---------|----------|
| `attack_skip_ms` | analysis | float | `100.0` | мс | Длительность пропуска в начале |
| `min_freq` | analysis | float | `50.0` | Гц | Минимальная сообщаемая частота |
| `max_freq` | analysis | float | `8000.0` | Гц | Максимальная сообщаемая частота |
| `prominence` | analysis | float | `0.005` | магнитуда | Минимальная выраженность пика |
| `distance` | analysis | int | `20` | бины | Минимальное число бинов между пиками |
| `smoothing_window` | analysis | int | `11` | отсчёты | Длина окна сглаживания |
| `fft_size` | analysis | int | `16384` | отсчёты | Размер FFT на кадр |
| `hop_size` | analysis | int | `2048` | отсчёты | Шаг между кадрами |
| `peak_count` | analysis | int | пусто | шт. | Максимум пиков; пусто — без ограничения |
| `spec_nperseg` | visualization | int | `4096` | отсчёты | Длина окна STFT |
| `spec_noverlap` | visualization | int | `3072` | отсчёты | Перекрытие STFT |
| `spec_nfft` | visualization | int | `4096` | отсчёты | Длина FFT для STFT |
| `spectrum_floor` | visualization | float | `-50.0` | дБ | Нижняя граница графика спектра |
| `spec_floor` | visualization | float | `-144.0` | дБ | Нижняя граница цветовой шкалы спектрограммы |
| `n_labels` | visualization | int | `7` | шт. | Число подписываемых сильнейших пиков |
| `format` | output | string | `csv` | — | Формат вывода: `csv` или `table` |

## Пример конфигурации

```ini
[analysis]
attack_skip_ms = 100.0
min_freq = 50.0
max_freq = 8000.0
prominence = 0.005
distance = 20
smoothing_window = 11
fft_size = 16384
hop_size = 2048
peak_count =

[visualization]
spec_nperseg = 4096
spec_noverlap = 3072
spec_nfft = 4096
spectrum_floor = -50.0
spec_floor = -144.0
n_labels = 7

[output]
format = csv
```

## Приоритет значений

```text
флаг CLI > значение из конфига > встроенное значение по умолчанию
```

Например, если в `analyze_bell.ini` задано `min_freq = 500.0`, но вы запускаете:

```bash
python analyze_bell.py samples/bell.wav --config analyze_bell.ini --min-freq 100.0
```

то итоговое значение `min_freq` будет `100.0`.

## Сохранение конфигурации

Чтобы записать текущую эффективную конфигурацию в файл, используйте `--save-config`:

```bash
# Записать в analyze_bell.ini в текущем каталоге
python analyze_bell.py --save-config

# Записать по указанному пути
python analyze_bell.py --save-config my_bell.ini
```

Полученный файл можно позже загрузить через `--config`. Пустое значение `peak_count` означает отсутствие ограничения.

## Флаги-действия

Такие флаги CLI, как `--visualize`, `--quiet` и `--no-show`, нельзя задать через INI-файл. Их нужно передавать в командной строке при необходимости.
