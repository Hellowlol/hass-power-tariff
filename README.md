# hass-power-tariff
Nothing here.



```
power_tariff:
  monitor_entity: "sensor.power_usage"
  tariffs:
    - name: dag
      limit_kwh: 1000
      over_limit_acceptance: 0.2
      over_limit_acceptance_seconds: 0.0

  devices:
    - turn_on: "some.entity_id_that_can_be_use_to_turn_device_on"
      turn_off: ""
      enabled: true
      assumed_usage: 100
      priority: 30
      power_usage: "some.entity_where_power_usage_is_state"
```
