"""
p_902_ai_helper.py - Спеціальний модуль для покращення документації під ШІ.
Генерує блок "ДЛЯ ШІ: Інтеграція та використання" у PROJECT_DOCUMENTATION.md.
"""

import os
import inspect
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging
import ast
import re
from datetime import datetime

def prepare_config_models():
    """Конфігурація не потрібна для цього модуля."""
    return {}

class AIHelperGenerator:
    """Генератор документації, оптимізованої для ШІ."""
    
    def __init__(self, app_context: Dict[str, Any]):
        self.app_context = app_context
        self.logger = logging.getLogger("AIHelper")
        self.project_root = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.docs_file = self.project_root / "PROJECT_DOCUMENTATION.md"
        
    def analyze_context_keys(self) -> List[str]:
        """Аналізує ключі в app_context та повертає описи."""
        context_info = []
        for key, value in self.app_context.items():
            if key.startswith('_'):
                continue
                
            value_type = type(value).__name__
            module = value.__class__.__module__ if hasattr(value, '__class__') else 'unknown'
            
            # Спрощений опис за типом
            if key == 'logger':
                desc = "Системний логер (logging.Logger)"
            elif key == 'config':
                desc = "Валідована конфігурація (Pydantic модель)"
            elif key == 'tts_engine':
                desc = "Головний двигун TTS синтезу"
            elif key == 'verbalizer':
                desc = "Вербалізатор цифр у слова"
            elif key == 'gradio_main_demo':
                desc = "Головний Gradio інтерфейс StyleTTS2"
            elif key == 'action_registry':
                desc = "Реєстр дій для GUI"
            elif 'tts' in key.lower():
                desc = "Компонент TTS системи"
            elif 'gradio' in key.lower() or 'gui' in key.lower():
                desc = "Графічний інтерфейс"
            else:
                desc = "Сервісний компонент"
            
            context_info.append(f"- `{key}` ({value_type}) - {desc}")
        
        return sorted(context_info)
    
    def generate_code_examples(self) -> str:
        """Генерує приклади коду для ШІ."""
        examples = []
        
        # Приклад 1: Як використовувати TTS
        examples.append("""
### 🎙️ Приклад 1: Базовий синтез мови
```python
# Отримати TTS двигун з контексту
tts_engine = app_context['tts_engine']

# Простий синтез
result = tts_engine.synthesize(
    text="Привіт, це тестовий синтез українською мовою.",
    speaker_id=1,
    speed=0.88
)

# Результат містить:
# - result['audio'] - numpy масив аудіо
# - result['sample_rate'] - частота дискретизації
# - result['duration'] - тривалість в секундах
# - result['output_path'] - шлях до збереженого файлу (якщо autosave=True)

# Зберегти аудіо у файл
import soundfile as sf
sf.write('output.wav', result['audio'], result['sample_rate'])
```""")

        # Приклад 2: Як використовувати Verbalizer
        examples.append("""
### 🔢 Приклад 2: Вербалізація тексту
```python
# Отримати вербалізатор
verbalizer = app_context.get('verbalizer')

if verbalizer:
    # Вербалізація тексту з цифрами
    text = "Зустріч відбудеться 22.08.2025 о 15:30."
    verbalized = verbalizer.generate_text(text)
    print(f"До: {text}")
    print(f"Після: {verbalized}")
    # Результат: "Зустріч відбудеться двадцять другого серпня дві тисячі двадцять п'ятого року о п'ятнадцять тридцять."
else:
    print("Verbalizer не активований в конфігурації")
```""")

        # Приклад 3: Як реєструвати дії
        examples.append("""
### 🎯 Приклад 3: Реєстрація власної дії
```python
from kod.p_080_registry import register_action

def my_custom_action(param1: str, param2: int = 10):
    \"\"\"Прикладна дія для мого модуля.\"\"\"
    return f"Виконано з {param1} та {param2}"

# Реєстрація дії в системі
register_action(
    app_context,
    action_id="my_module.custom_action",
    name="Моя кастомна дія",
    callback=my_custom_action,
    description="Демонстраційна дія для прикладу",
    module="p_XXX_my_module",  # Замінити на реальну назву модуля
    category="Мій модуль",
    requires_confirmation=True
)

# Дія буде доступна в GUI через реєстр дій
```""")

        # Приклад 4: Як створити простий модуль
        examples.append("""
### 🧩 Приклад 4: Створення нового модуля
```python
# p_250_my_feature.py
from typing import Dict, Any
from pydantic import BaseModel
import logging

# 1. Клас конфігурації
class MyFeatureConfig(BaseModel):
    enabled: bool = True
    message: str = "Привіт від мого модуля!"
    timeout: int = 30

# 2. Функція для конфігурації
def prepare_config_models():
    return {'my_feature': MyFeatureConfig}

# 3. Обов'язкова функція ініціалізації
def initialize(app_context: Dict[str, Any]):
    logger = app_context.get('logger', logging.getLogger("MyFeature"))
    
    # Отримати конфігурацію
    config = app_context.get('config')
    if config and hasattr(config, 'my_feature'):
        my_config = config.my_feature
        if not my_config.enabled:
            logger.info("Мій модуль вимкнено в конфігурації")
            return None
    
    # Логіка модуля
    logger.info(f"Мій модуль запущено! Повідомлення: {my_config.message}")
    
    # Додати свій сервіс в контекст
    app_context['my_feature'] = {
        'greet': lambda name: f"{my_config.message} Радий бачити, {name}!",
        'config': my_config
    }
    
    return app_context['my_feature']

# 4. Опційна функція очищення
def stop(app_context: Dict[str, Any]):
    if 'my_feature' in app_context:
        del app_context['my_feature']
    logger = app_context.get('logger')
    if logger:
        logger.info("Мій модуль зупинено")
```""")

        # Приклад 5: Як запустити GUI
        examples.append("""
### 🌐 Приклад 5: Запуск графічного інтерфейсу
```python
# Спосіб 1: Через GUI менеджер (рекомендовано)
gui_manager = app_context.get('gui_manager')
if gui_manager:
    # Запустити конкретний GUI
    gui_manager.start_gui('p_305_tts_gradio_main')
    # або
    gui_manager.start_gui('p_350_tts_gradio')

# Спосіб 2: Безпосередньо через демо
if 'gradio_main_demo' in app_context:
    demo = app_context['gradio_main_demo']
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True
    )

# Спосіб 3: Через CLI меню (автоматичний)
# Просто запустіть main.py і виберіть інтерфейс з меню
```""")

        return "\n".join(examples)
    
    def generate_faq(self) -> str:
        """Генерує FAQ для ШІ."""
        faq = """
### ❓ Часті питання (FAQ)

**Q1: Як додати новий голос у систему?**
```
1. Помістіть .pt файл з голосом у папку voices/
2. Назвіть файл унікально (наприклад, my_voice.pt)
3. Система автоматично виявить його при запуску
4. У Gradio інтерфейсі виберіть ваш голос з випадаючого списку
```

**Q2: Як змінити швидкість синтезу за замовчуванням?**
```
1. Відкрийте config.yaml
2. Знайдіть секцію tts:
3. Змініть значення default_speed:
   tts:
     default_speed: 0.95  # Замість 0.88
4. Збережіть файл та перезапустіть систему
```

**Q3: Як активувати вербалізатор?**
```
1. У config.yaml знайдіть секцію verbalizer
2. Змініть enabled на true:
   verbalizer:
     enabled: true
     device: auto
3. Система автоматично завантажить модель при наступному запуску
```

**Q4: Як додати звуковий ефект (SFX)?**
```
1. Створіть/відредагуйте файл sfx.yaml
2. Додайте конфігурацію для вашого звуку:
   sounds:
     my_sound:
       file: sounds/my_sound.wav
       gain_db: 0.0
       normalize: true
3. У тексті використовуйте тег: #my_sound
```

**Q5: Як відлагодити проблему з модулем?**
```
1. Перевірте лог файл: logs/app.log
2. Перевірте, чи модуль має префікс p_XXX_ у назві
3. Переконайтеся, що є функція initialize(app_context)
4. У config.yaml перевірте, чи enabled: true для вашого модуля
5. Перезапустіть систему з debug режимом:
   app:
     mode: DEBUG
```
"""
        return faq
    
    def generate_context_map(self) -> str:
        """Генерує мапу ключів app_context."""
        if not self.app_context:
            return "⚠️ App context не доступний для аналізу"
        
        map_content = ["### 🗺️ Мапа ключів app_context\n"]
        
        # Групуємо за категоріями
        categories = {
            'Конфігурація': [],
            'Сервіси': [],
            'TTS компоненти': [],
            'Графічні інтерфейси': [],
            'Утиліти': [],
            'Інше': []
        }
        
        for key, value in sorted(self.app_context.items()):
            if key.startswith('_'):
                continue
                
            value_type = type(value).__name__
            desc = self._get_component_description(key, value)
            
            # Визначаємо категорію
            if 'config' in key.lower():
                cat = 'Конфігурація'
            elif 'tts' in key.lower() or 'verbalizer' in key.lower():
                cat = 'TTS компоненти'
            elif 'gui' in key.lower() or 'gradio' in key.lower() or 'demo' in key.lower():
                cat = 'Графічні інтерфейси'
            elif key in ['logger', 'event_bus', 'action_registry', 'error_handler']:
                cat = 'Сервіси'
            elif key in ['project_info', 'universal_deps_checker']:
                cat = 'Утиліти'
            else:
                cat = 'Інше'
            
            categories[cat].append(f"  - `{key}` - {desc} ({value_type})")
        
        # Виводимо категорії
        for category, items in categories.items():
            if items:
                map_content.append(f"\n**{category}:**")
                map_content.extend(items)
        
        return "\n".join(map_content)
    
    def _get_component_description(self, key: str, value: Any) -> str:
        """Повертає опис компонента за ключем."""
        descriptions = {
            'logger': 'Центральний логер системи',
            'config': 'Головна конфігурація (Pydantic)',
            'tts_engine': 'Двигун синтезу мови',
            'tts_models': 'Менеджер моделей TTS',
            'verbalizer': 'Вербалізатор тексту',
            'gradio_main_demo': 'Головний інтерфейс Gradio',
            'action_registry': 'Реєстр дій для GUI',
            'event_bus': 'Шина подій для модулів',
            'error_handler': 'Обробник помилок модулів',
            'universal_deps_checker': 'Перевірка залежностей',
            'project_info': 'Інформація про проект',
            'gui_manager': 'Менеджер графічних інтерфейсів',
        }
        
        return descriptions.get(key, 'Сервісний компонент системи')
    
    def generate_workflow_diagram(self) -> str:
        """Генерує діаграму робочого процесу для ШІ."""
        return """
### 🔄 Робочий процес TTS системи

```mermaid
graph TD
    A[Вхідний текст] --> B{Містить цифри/дати?}
    B -->|Так| C[Вербалізатор]
    B -->|Ні| D[Прямий синтез]
    C --> E[Вербалізований текст]
    D --> F[Оригінальний текст]
    E --> G[Обробка тегів #gN/#sfx]
    F --> G
    G --> H[Розбиття на частини]
    H --> I[TTS синтез]
    I --> J[Нормалізація гучності]
    J --> K[Додавання SFX]
    K --> L[Вихідне аудіо]
    
    M[Файл голосу .pt] --> I
    N[SFX конфігурація] --> K
    
    style A fill:#e1f5fe
    style L fill:#e8f5e8
```
"""
    
    def add_ai_section_to_docs(self):
        """Додає секцію для ШІ у документацію."""
        self.logger.info("Додавання секції для ШІ у документацію...")
        
        # Зчитуємо поточну документацію
        if not self.docs_file.exists():
            self.logger.error(f"Файл документації не знайдено: {self.docs_file}")
            return
        
        with open(self.docs_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Генеруємо нову секцію
        ai_section = self.generate_ai_section()
        
        # Знаходимо місце для вставки (перед останніми правилами розробки)
        # Або додаємо в кінець
        marker = "## 📝 ПРАВИЛА РОЗРОБКИ ДЛЯ ШІ"
        
        if marker in content:
            # Вставляємо перед правилами розробки
            parts = content.split(marker)
            new_content = parts[0] + ai_section + "\n\n" + marker + parts[1]
        else:
            # Додаємо в кінець
            new_content = content + "\n\n" + ai_section
        
        # Зберігаємо оновлений файл
        with open(self.docs_file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        self.logger.info(f"✅ Секція для ШІ додана до {self.docs_file.name}")
    
    def generate_ai_section(self) -> str:
        """Генерує повну секцію для ШІ."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        section = f"""## 🤖 ДЛЯ ШІ: Інтеграція та використання
*Автоматично згенеровано: {timestamp}*
*Ця секція призначена для AI-помічників (ChatGPT, Claude, тощо)*

---

{self.generate_context_map()}

---

{self.generate_workflow_diagram()}

---

{self.generate_code_examples()}

---

{self.generate_faq()}

---

### 🔍 Як аналізувати цю систему для ШІ:

1. **Розуміння архітектури:**
   - Система модульна з префіксами `p_XXX_name.py`
   - Кожен модуль реєструє себе в `app_context`
   - Конфігурація автоматично збирається з усіх модулів

2. **Пошук функціональності:**
   - TTS: Шукайте модулі з префіксом `p_3XX`
   - Конфігурація: `p_01X` та `p_02X`
   - Графічні інтерфейси: `p_3XX_gradio`
   - Утиліти: `p_1XX` та `p_9XX`

3. **Відлагодження:**
   - Логи: `logs/app.log`
   - Конфігурація: `config.yaml`
   - Автодокументація: `PROJECT_DOCUMENTATION.md`

4. **Розширення системи:**
   - Додайте новий модуль з унікальним префіксом
   - Реалізуйте обов'язкову функцію `initialize(app_context)`
   - Зареєструйте сервіс в `app_context`
   - Додайте конфігурацію через `prepare_config_models()`

---

### 💎 Короткий шпаргалка для ШІ:

**Запуск системи:** `python main.py`
**Перегляд конфігурації:** `python -m kod.p_015_config_tool show`
**Оновлення конфігурації:** `python -m kod.p_012_config_updater update`
**Документація:** Прочитайте `PROJECT_DOCUMENTATION.md` (цей файл)

**Основні компоненти:**
- `app_context['tts_engine']` - головний API для синтезу
- `app_context['config']` - доступ до всіх налаштувань
- `app_context['logger']` - для логування
- `app_context['action_registry']` - для реєстрації дій GUI

---
"""
        return section

def initialize(app_context: Dict[str, Any]):
    """Ініціалізація AI Helper модуля."""
    logger = app_context.get('logger', logging.getLogger("AIHelper"))
    logger.info("🤖 Ініціалізація AI Helper (покращення документації для ШІ)...")
    
    # Створюємо генератор
    helper = AIHelperGenerator(app_context)
    
    # Додаємо секцію в документацію
    helper.add_ai_section_to_docs()
    
    # Додаємо в контекст для можливості повторного використання
    app_context['ai_helper'] = {
        'regenerate_docs': helper.add_ai_section_to_docs,
        'get_context_info': helper.generate_context_map,
        'get_code_examples': helper.generate_code_examples
    }
    
    logger.info("✅ AI Helper успішно ініціалізовано")
    return helper

def stop(app_context: Dict[str, Any]) -> None:
    """Зупинка модуля AI Helper."""
    if 'ai_helper' in app_context:
        del app_context['ai_helper']
    
    logger = app_context.get('logger')
    if logger:
        logger.info("AI Helper зупинено")