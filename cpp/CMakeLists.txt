cmake_minimum_required(VERSION 3.20)
project(SatelliteGroundStation)

# C++17 standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find librtlsdr
# On Apple Silicon Macs, Homebrew installs to /opt/homebrew
set(RTLSDR_INCLUDE_DIR "/opt/homebrew/include")
set(RTLSDR_LIBRARY "/opt/homebrew/lib/librtlsdr.dylib")

# Include directories
include_directories(${CMAKE_SOURCE_DIR}/include)
include_directories(${RTLSDR_INCLUDE_DIR})

# Test program: rtlsdr_test
add_executable(rtlsdr_test src/rtlsdr_test.cpp)
target_link_libraries(rtlsdr_test ${RTLSDR_LIBRARY})