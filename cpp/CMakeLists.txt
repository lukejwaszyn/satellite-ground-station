cmake_minimum_required(VERSION 3.14)
project(satellite_ground_station)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find RTL-SDR library
find_path(RTLSDR_INCLUDE_DIR rtl-sdr.h
    HINTS /opt/homebrew/include /usr/local/include /usr/include
)

find_library(RTLSDR_LIBRARY rtlsdr
    HINTS /opt/homebrew/lib /usr/local/lib /usr/lib
)

if(NOT RTLSDR_INCLUDE_DIR OR NOT RTLSDR_LIBRARY)
    message(FATAL_ERROR "RTL-SDR library not found")
endif()

message(STATUS "RTL-SDR include: ${RTLSDR_INCLUDE_DIR}")
message(STATUS "RTL-SDR library: ${RTLSDR_LIBRARY}")

include_directories(${RTLSDR_INCLUDE_DIR})

# Threads required for capture
find_package(Threads REQUIRED)

# RTL-SDR test executable
add_executable(rtlsdr_test src/rtlsdr_test.cpp)
target_link_libraries(rtlsdr_test ${RTLSDR_LIBRARY})

# Real-time capture executable
add_executable(rtlsdr_capture src/rtlsdr_capture.cpp)
target_link_libraries(rtlsdr_capture ${RTLSDR_LIBRARY} Threads::Threads)

# Doppler tracker executable
add_executable(doppler_tracker src/doppler_tracker.cpp)
target_link_libraries(doppler_tracker ${RTLSDR_LIBRARY} Threads::Threads)

# Install targets
install(TARGETS rtlsdr_test rtlsdr_capture doppler_tracker
    RUNTIME DESTINATION bin
)
