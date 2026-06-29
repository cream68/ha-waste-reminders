# ha waste reminders

Custom integration for Home Assistant.

## HACS structure

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
│       ├── strings.json
│       └── translations/
├── hacs.json
└── README.md
```

## Notes

Local development runs from:

`config/custom_components/ha_waste_reminders/`

For GitHub/HACS, publish only:

`custom_components/ha_waste_reminders/`
