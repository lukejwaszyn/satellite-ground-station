cmake_minimum_required(VERSION 3.10)
project(satellite_ground_station)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find librtlsdr
find_library(RTLSDR_LIBRARY rtlsdr HINTS /opt/homebrew/lib /usr/local/lib)
find_path(RTLSDR_INCLUDE_DIR rtl-sdr.h HINTS /opt/homebrew/include /usr/local/include)

if(NOT RTLSDR_LIBRARY)
    message(FATAL_ERROR "librtlsdr not found. Install with: brew install librtlsdr")
endif()

include_directories(${RTLSDR_INCLUDE_DIR})

# RTL-SDR test executable
add_executable(rtlsdr_test src/rtlsdr_test.cpp)
target_link_libraries(rtlsdr_test ${RTLSDR_LIBRARY})

# Future executables
# add_executable(rtlsdr_capture src/rtlsdr_capture.cpp)
# target_link_libraries(rtlsdr_capture ${RTLSDR_LIBRARY})

# add_executable(doppler_tracker src/doppler_tracker.cpp)
# target_link_libraries(doppler_tracker ${RTLSDR_LIBRARY})
