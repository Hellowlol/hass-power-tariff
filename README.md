# hass-power-tariff

Just a experiment, nothing else. 


```
power_tariff:
  # Required
  monitor_entity: "sensor.power_usage"
  tariffs:
      # Required
    - name: dag
      # Required
      limit_kwh: 3500
      # Optional, default True
      enabled: true
      # Optional: default 0.0
      over_limit_acceptance: 0.1
      # Optional: default 0.0
      over_limit_acceptance_seconds: 60.0
      # Optional: if missing, sets default values 
      restrictions:
        # Optional
        date: 
          # Optional: default 01.01
          start: "15.01"
          # Optional: default 31.12
          end: "12.12"
        # Optional: if missing sets defaults
        time:
          # Optional: default 00:00:00
          start: "00:00:00"
          # Optional, default 23:59:59
          end: "23:59:59"
        # Optional, defaults: ["mon", "tue", "wes", "thu", "fri", "sat", "sun"]
        weekday:
          - "sun"
          
  devices:
      # Required
    - turn_on: "switch.stor_kule"
      # Optional, defaults the value of turn_on if missing
      turn_off: "switch.stor_kule"
      # Optional: default: True
      enabled: true
      # Optional: default 0.0, Use if the entity dont have power_usage
      # can also be usefull for testing
      assumed_usage: 300.0
      # Optional: default 10, range 1 - 100, the higher the less likely to turn off the device
      priority: 30
      # Optional: default ""
      power_usage: "some.entity_where_power_usage_is_state"
```
