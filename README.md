# hass-power-tariff

Just a experiment, nothing else. 


```
power_tariff:
  monitor_entity: "sensor.power_usage"
  tariffs:
    - name: dag
      limit_kwh: 1000
      enabled: true
      over_limit_acceptance: 0.2
      over_limit_acceptance_seconds: 30.0
      days:
        - weekday: mon
          start: "00:00"
          end: "23:59"
    - name: natt
      limit_kwh: 5000
      enabled: false
      over_limit_acceptance: 0.2
      over_limit_acceptance_seconds: 0.0
      days:
        - weekday: mon
          start: "00:00"
          end: "23:59"
        - weekday: sun
          start: "00:00:00"
          end: "23:59:59"


  devices:
    - turn_on: "scene.123"
      turn_off: "scene.321"
      enabled: true
      assumed_usage: 100.0
      priority: 30
      power_usage: "some.entity_where_power_usage_is_state"
```
