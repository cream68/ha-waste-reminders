# ha waste reminders

Custom Integration fuer Home Assistant.

## HACS Repo-Struktur

Damit HACS die Integration installieren kann, muss dein GitHub-Repository so aufgebaut sein:

```text
.
├── custom_components/
│   └── ha_waste_reminders/
│       ├── __init__.py
│       ├── manifest.json
│       ├── config_flow.py
│       ├── coordinator.py
│       ├── sensor.py
│       ├── switch.py
│       ├── time.py
│       ├── button.py
│       ├── select.py
│       ├── entity.py
│       ├── const.py
│       ├── utils.py
│       └── strings.json
├── hacs.json
└── README.md
```

## Wichtig

Die lokale Entwicklungsstruktur unter `config/custom_components/ha_waste_reminders/` ist fuer deine Home-Assistant-Instanz korrekt.

Fuer GitHub und HACS musst du aber nur den Ordner `ha_waste_reminders` in ein Repo-Root unter `custom_components/` legen.

Diese Ordner und Dateien solltest du nicht ins HACS-Repo uebernehmen:

- `config/.storage/`
- `config/home-assistant.log`
- `config/home-assistant.log.1`
- `config/tts/`
- `config/blueprints/`
