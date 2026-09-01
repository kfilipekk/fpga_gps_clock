idf_component_register(SRCS "cc1101_sensor.c" INCLUDE_DIRS "."
                       REQUIRES esp_driver_gpio esp_driver_tsens esp_driver_i2s esp_timer esp_driver_rmt)
