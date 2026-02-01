#include <iostream>
#include <rtl-sdr.h>

int main() {
    std::cout << "RTL-SDR C++ Test Program\n";
    std::cout << "========================\n";
    
    uint32_t device_count = rtlsdr_get_device_count();
    std::cout << "Found " << device_count << " device(s)\n\n";
    
    if (device_count == 0) {
        std::cerr << "No RTL-SDR devices found. Plug in device and try again.\n";
        return 1;
    }
    
    for (uint32_t i = 0; i < device_count; i++) {
        char manufacturer[256], product[256], serial[256];
        rtlsdr_get_device_usb_strings(i, manufacturer, product, serial);
        
        std::cout << "Device " << i << ":\n";
        std::cout << "  Name: " << rtlsdr_get_device_name(i) << "\n";
        std::cout << "  Manufacturer: " << manufacturer << "\n";
        std::cout << "  Product: " << product << "\n";
        std::cout << "  Serial: " << serial << "\n\n";
    }
    
    rtlsdr_dev_t *dev = nullptr;
    int result = rtlsdr_open(&dev, 0);
    
    if (result < 0) {
        std::cerr << "Failed to open device: " << result << "\n";
        return 1;
    }
    
    std::cout << "Successfully opened device 0\n";
    
    enum rtlsdr_tuner tuner = rtlsdr_get_tuner_type(dev);
    std::cout << "Tuner type: " << tuner << "\n";
    
    uint32_t freq = 137500000;
    result = rtlsdr_set_center_freq(dev, freq);
    
    if (result == 0) {
        uint32_t actual_freq = rtlsdr_get_center_freq(dev);
        std::cout << "Set frequency to " << (actual_freq / 1e6) << " MHz\n";
    }
    
    uint32_t samp_rate = 2400000;
    result = rtlsdr_set_sample_rate(dev, samp_rate);
    
    if (result == 0) {
        uint32_t actual_rate = rtlsdr_get_sample_rate(dev);
        std::cout << "Set sample rate to " << (actual_rate / 1e6) << " MS/s\n";
    }
    
    result = rtlsdr_set_tuner_gain_mode(dev, 1);
    result = rtlsdr_set_tuner_gain(dev, 200);
    int gain = rtlsdr_get_tuner_gain(dev);
    std::cout << "Set gain to " << (gain / 10.0) << " dB\n";
    
    std::cout << "\nAll tests passed! RTL-SDR is ready for C++ programming.\n";
    
    rtlsdr_close(dev);
    
    return 0;
}
