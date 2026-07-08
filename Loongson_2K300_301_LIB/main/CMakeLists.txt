cmake_minimum_required(VERSION 3.16)

if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/toolchain_path.cmake")
    include("${CMAKE_CURRENT_SOURCE_DIR}/toolchain_path.cmake")
endif()

set(CMAKE_C_COMPILER "${CMAKE_TOOLCHAIN_PATH}/bin/loongarch64-linux-gnu-gcc")
set(CMAKE_CXX_COMPILER "${CMAKE_TOOLCHAIN_PATH}/bin/loongarch64-linux-gnu-g++")
set(PROJECT_NAME "main")

project(${PROJECT_NAME} C CXX)

set(SRC
    ${PROJECT_SOURCE_DIR}/main.cpp
    ${PROJECT_SOURCE_DIR}/../libraries/app/lq_mqtt.cpp
    ${PROJECT_SOURCE_DIR}/../libraries/app/lq_sgp30.cpp
    ${PROJECT_SOURCE_DIR}/../libraries/app/lq_sht30.cpp
    ${PROJECT_SOURCE_DIR}/../libraries/common/src/lq_base_class.cpp
    ${PROJECT_SOURCE_DIR}/../libraries/common/src/lq_i2c_dev.cpp
    ${PROJECT_SOURCE_DIR}/../libraries/common/src/lq_utils.cpp
    ${PROJECT_SOURCE_DIR}/../libraries/drv/src/lq_fs_i2c.cpp
    ${PROJECT_SOURCE_DIR}/../libraries/drv/src/lq_map_addr.cpp
    ${PROJECT_SOURCE_DIR}/../libraries/drv/src/lq_reg_adc.cpp
    ${PROJECT_SOURCE_DIR}/../libraries/drv/src/lq_reg_gpio.cpp
    ${PROJECT_SOURCE_DIR}/../libraries/drv/src/lq_signal_handle.cpp
)

add_executable(${PROJECT_NAME} ${SRC})

target_include_directories(${PROJECT_NAME} PRIVATE
    ${PROJECT_SOURCE_DIR}
    ${PROJECT_SOURCE_DIR}/../libraries/app
    ${PROJECT_SOURCE_DIR}/../libraries/common/inc
    ${PROJECT_SOURCE_DIR}/../libraries/drv/inc
)

target_link_libraries(${PROJECT_NAME} PUBLIC
    pthread
    m
)
