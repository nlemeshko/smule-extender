# smule-extender

Скрипт для автоматизации Smule через ADB по сети: подключается к `192.168.2.105:5555`, запускает Smule, переходит на вкладку `Profile`, скроллит вниз до конца и нажимает все кнопки `Extend` с resource-id `com.smule.singandroid:id/btn_cta_active`. В конце или при ошибке приложение принудительно останавливается.

## Требования
- Python 3.10+
- Установленный `adb` в PATH (`Android Platform Tools`)
- Смартфон с включённой отладкой по USB/TCPIP и доступом по `192.168.2.105:5555`

## Установка
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Запуск
```bash
python main.py
```

При необходимости измените константы `DEVICE`, `PACKAGE` в `main.py`.
