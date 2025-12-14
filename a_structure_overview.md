# Структура розподіленого проекту

Структура могла частково змінитися

## 📁 Рівні абстракції

### 🎨 **Рівень 1: UI Компоненти** (`a_1_*`)
Кожен файл = один UI-блок, незалежний від інших:

- **`a_1_1_ui_text_input.py`**
  - `create_text_input_block()` → (textbox, file)

- **`a_1_2_ui_speakers.py`**
  - `create_speaker_block(choices)` → (voices[], speeds[], accords[])

- **`a_1_3_ui_controls.py`**
  - `create_controls_block()` → (btn_start, save_option, ignore_speed)

- **`a_1_4_ui_output.py`**
  - `create_output_block()` → (audio, slider, timers...)

- **`a_1_5_ui_syntax_help.py`**
  - `create_syntax_help_block()` → (markdown спойлер)

- **`a_1_6_ui_settings_save.py`**
  - `create_settings_save_block()` → (download_btn, save_btn, load_btn) x2

- **`a_1_ui_main.py`** ⭐ (МОНТАЖНИК)
  - `create_multi_dialog_tab()` → збирає всі блоки
  - `setup_text_change_handlers()` → обробники зміни тексту

---

### ⚙️ **Рівень 2: Обробки & Логіка** (`a_2_-_a_7_`)

- **`a_2_synthesis.py`**
  - `_synthesize_chunk()` — синтез з fallback-ами
  - Залежить від: `a_6_*`, `a_7_*`

- **`a_3_sfx_engine.py`**
  - `get_sfx_config()` — читання sfx.yaml
  - `_load_and_process_sfx()` — завантаження SFX з обробкою
  - Залежить від: numpy, scipy, soundfile

- **`a_4_progress_logic.py`**
  - `estimate_remaining()` — прогноз часу
  - `get_elapsed_str()` — форматування часу
  - Залежить від: `a_7_utils.format_hms`

- **`a_5_speaker_logic.py`**
  - `parse_script_events()` — парсинг тегів `#gN`, `#sfx`
  - `_compute_speed_effective()` — обчислення швидкості
  - Залежить від: `a_6_text_processing`

- **`a_6_text_processing.py`**
  - `normalize_text()` — нормалізація юнікоду
  - `split_to_parts()` — розбиття по токенам
  - Залежить від: albert-base-v2 tokenizer (опціонально)

- **`a_7_utils.py`**
  - `NoProgress` — мінімальна заглушка
  - `_safe_float()`, `_read_text_source()`, `_should_use_single_voice()`
  - `format_hms()` — форматування часу
  - Залежить від: нічого

---

### 🎼 **Рівень 3: Оркестрація & Обробники** (`a_8_*`)

- **`a_8_pipeline.py`** ⭐ (БАТЧ-СИНТЕЗ)
  - `batch_synthesize_dialog_events()` — основний генератор
  - Виклик: text → парсинг → синтез/SFX → файли + UI-оновлення
  - Залежить від: `a_2_*`, `a_3_*`, `a_4_*`, `a_5_*`, `a_7_*`

- **`a_8_1_event_handlers.py`**
  - `create_btn_start_handler()` — обробник кнопки запуску
  - `create_export_settings_handler()` — експорт налаштувань
  - `create_save_to_default_handler()` — збереження в папку
  - `create_load_settings_handler()` — завантаження з файлу
  - `create_part_slider_handler()` — зміна слайдера частин

- **`a_8_2_event_registration.py`** ⭐ (РЕЄСТР ПОДІЙ)
  - `register_all_events()` — з'єднує click/change обробники з UI
  - Залежить від: `a_8_1_*`

---

### 🚀 **Рівень 4: Запуск** (`a_9_*`)

- **`a_9_main.py`** ⭐ (ТОЧКА ВХОДУ)
  - `main()` — створює Gradio інтерфейс
  - Послідовність:
    1. Створити UI компоненти (`a_1_ui_main`)
    2. Налаштувати обробники текстових змін
    3. Зібрати словник компонентів
    4. Реєструвати всі события (`a_8_2_event_registration`)
    5. Запустити `demo.queue().launch()`

---

## 🔄 Потік даних

```
Користувач вводить текст/файл
    ↓
Натискає кнопку "Розпочати"
    ↓
a_8_1_event_handlers.create_btn_start_handler()
    ↓
a_8_pipeline.batch_synthesize_dialog_events()
    ├─ a_5_speaker_logic.parse_script_events()
    ├─ (для кожної eventi:)
    │  ├─ a_2_synthesis._synthesize_chunk() [ИЛИ]
    │  └─ a_3_sfx_engine._load_and_process_sfx()
    ├─ a_4_progress_logic.estimate_remaining()
    └─ yield (audio_file, updates...)
    ↓
UI оновлюється у реальному часі
```

---

## ✅ Залежності між файлами

```
a_9_main.py (главна точка входу)
├── a_1_ui_main.py
│   ├── a_1_1_ui_text_input.py
│   ├── a_1_2_ui_speakers.py
│   ├── a_1_3_ui_controls.py
│   ├── a_1_4_ui_output.py
│   ├── a_1_5_ui_syntax_help.py
│   └── a_1_6_ui_settings_save.py
│
├── a_8_pipeline.py
│   ├── a_2_synthesis.py
│   │   ├── a_6_text_processing.py
│   │   └── a_7_utils.py
│   ├── a_3_sfx_engine.py
│   ├── a_4_progress_logic.py
│   │   └── a_7_utils.py
│   ├── a_5_speaker_logic.py
│   │   └── a_6_text_processing.py
│   └── a_7_utils.py
│
└── a_8_2_event_registration.py
    └── a_8_1_event_handlers.py
        ├── a_8_pipeline.py (передається як параметр)
        ├── a_3_sfx_engine.py
        └── (опціонально): a_8_1_event_handlers.py
```

---

## 🎯 Як розширювати

### Додати новий UI-блок:
1. Створити `a_1_7_ui_new_feature.py` з функцією `create_new_block()`
2. Імпортувати в `a_1_ui_main.py`
3. Додати компоненти до `create_multi_dialog_tab()`

### Додати новий обробник:
1. Додати функцію в `a_8_1_event_handlers.py`
2. Зареєструвати в `a_8_2_event_registration.py`

### Змінити логіку синтезу:
1. Змінити `a_2_synthesis.py` або `a_8_pipeline.py`
2. Імпорти автоматично відстежать зміни

---

## 📝 Файли, які потрібні від користувача

**Зовні цього проекту:**
- `app.py` — має містити:
  - `synthesize(mode, text, speed, voice_name, progress)`
  - `prompts_list` — список голосів
- `sfx.yaml` — конфіг SFX файлів
- звукові файли для SFX

---

## 🏃 Запуск

```bash
python a_9_main.py
```

Або в коді:
```python
from a_9_main import main
main()
```

---

**Переваги цієї структури:**
✅ Кожен файл має одну відповідальність  
✅ Легко тестувати окремо  
✅ Легко додавати нові UI-блоки  
✅ Легко змінювати логіку без переписування UI  
✅ Ясна ієрархія залежностей  
✅ Готово до масштабування
