/*
 * doppler_tracker.cpp
 * Satellite Ground Station - Real-time Doppler Frequency Tracker
 *
 * Reads Doppler profile from JSON, adjusts RTL-SDR frequency in real-time
 * during satellite pass to compensate for Doppler shift.
 *
 * Author: Luke Waszyn
 * Date: February 2026
 */

#include <rtl-sdr.h>
#include <iostream>
#include <fstream>
#include <sstream>
#include <vector>
#include <string>
#include <thread>
#include <atomic>
#include <chrono>
#include <cmath>
#include <csignal>
#include <getopt.h>

// Simple JSON value extraction (no external dependency)
// Only handles the specific format from doppler_calc.py
class SimpleJSON {
public:
    bool load(const std::string& filename) {
        std::ifstream file(filename);
        if (!file) return false;
        
        std::stringstream buffer;
        buffer << file.rdbuf();
        content_ = buffer.str();
        return true;
    }
    
    double getDouble(const std::string& key) {
        std::string search = "\"" + key + "\":";
        size_t pos = content_.find(search);
        if (pos == std::string::npos) return 0.0;
        
        pos += search.length();
        while (pos < content_.size() && (content_[pos] == ' ' || content_[pos] == '\t'))
            pos++;
        
        size_t end = pos;
        while (end < content_.size() && (isdigit(content_[end]) || content_[end] == '.' || 
               content_[end] == '-' || content_[end] == 'e' || content_[end] == 'E' || content_[end] == '+'))
            end++;
        
        return std::stod(content_.substr(pos, end - pos));
    }
    
    std::vector<double> getArray(const std::string& key) {
        std::vector<double> result;
        std::string search = "\"" + key + "\":";
        size_t pos = content_.find(search);
        if (pos == std::string::npos) return result;
        
        pos = content_.find('[', pos);
        if (pos == std::string::npos) return result;
        
        size_t end = content_.find(']', pos);
        if (end == std::string::npos) return result;
        
        std::string array_str = content_.substr(pos + 1, end - pos - 1);
        std::stringstream ss(array_str);
        std::string item;
        
        while (std::getline(ss, item, ',')) {
            try {
                // Trim whitespace
                size_t start = item.find_first_not_of(" \t\n\r");
                size_t stop = item.find_last_not_of(" \t\n\r");
                if (start != std::string::npos && stop != std::string::npos) {
                    result.push_back(std::stod(item.substr(start, stop - start + 1)));
                }
            } catch (...) {
                // Skip invalid entries
            }
        }
        return result;
    }
    
private:
    std::string content_;
};

// Doppler profile data
struct DopplerProfile {
    double center_freq_hz;
    double time_step_sec;
    std::vector<double> times_sec;
    std::vector<double> doppler_hz;
    
    bool load(const std::string& filename) {
        SimpleJSON json;
        if (!json.load(filename)) {
            std::cerr << "Error: Cannot load Doppler profile: " << filename << std::endl;
            return false;
        }
        
        center_freq_hz = json.getDouble("center_freq_hz");
        time_step_sec = json.getDouble("time_step_sec");
        times_sec = json.getArray("times_sec");
        doppler_hz = json.getArray("doppler_hz");
        
        if (times_sec.empty() || doppler_hz.empty()) {
            std::cerr << "Error: Empty Doppler profile" << std::endl;
            return false;
        }
        
        if (times_sec.size() != doppler_hz.size()) {
            std::cerr << "Error: Mismatched array sizes in Doppler profile" << std::endl;
            return false;
        }
        
        return true;
    }
    
    // Interpolate Doppler shift at given time
    double getDoppler(double time_sec) {
        if (times_sec.empty()) return 0.0;
        
        // Before first point
        if (time_sec <= times_sec.front()) return doppler_hz.front();
        
        // After last point
        if (time_sec >= times_sec.back()) return doppler_hz.back();
        
        // Linear interpolation
        for (size_t i = 1; i < times_sec.size(); i++) {
            if (time_sec <= times_sec[i]) {
                double t0 = times_sec[i-1];
                double t1 = times_sec[i];
                double d0 = doppler_hz[i-1];
                double d1 = doppler_hz[i];
                
                double alpha = (time_sec - t0) / (t1 - t0);
                return d0 + alpha * (d1 - d0);
            }
        }
        
        return doppler_hz.back();
    }
    
    double getDuration() {
        if (times_sec.empty()) return 0.0;
        return times_sec.back();
    }
};

// Global state
static std::atomic<bool> g_running(true);
static rtlsdr_dev_t* g_dev = nullptr;

void signal_handler(int signum) {
    std::cerr << "\nSignal " << signum << " received, stopping..." << std::endl;
    g_running = false;
}

void print_usage(const char* progname) {
    std::cout << "Usage: " << progname << " [options] -p <doppler_profile.json>\n"
              << "\nOptions:\n"
              << "  -p <file>      Doppler profile JSON (required)\n"
              << "  -D <device>    Device index (default: 0)\n"
              << "  -u <interval>  Update interval in ms (default: 100)\n"
              << "  -n             Dry run - don't actually tune\n"
              << "  -h             Show this help\n"
              << "\nThe Doppler profile is generated by doppler_calc.py\n";
}

int main(int argc, char* argv[]) {
    std::string profile_file;
    int device_index = 0;
    int update_interval_ms = 100;
    bool dry_run = false;
    
    // Parse arguments
    int opt;
    while ((opt = getopt(argc, argv, "p:D:u:nh")) != -1) {
        switch (opt) {
            case 'p':
                profile_file = optarg;
                break;
            case 'D':
                device_index = std::stoi(optarg);
                break;
            case 'u':
                update_interval_ms = std::stoi(optarg);
                break;
            case 'n':
                dry_run = true;
                break;
            case 'h':
            default:
                print_usage(argv[0]);
                return (opt == 'h') ? 0 : 1;
        }
    }
    
    if (profile_file.empty()) {
        std::cerr << "Error: Doppler profile required (-p)\n";
        print_usage(argv[0]);
        return 1;
    }
    
    // Load Doppler profile
    DopplerProfile profile;
    if (!profile.load(profile_file)) {
        return 1;
    }
    
    std::cout << "Doppler Profile Loaded:\n";
    std::cout << "  Center frequency: " << profile.center_freq_hz / 1e6 << " MHz\n";
    std::cout << "  Duration: " << profile.getDuration() << " seconds\n";
    std::cout << "  Points: " << profile.times_sec.size() << "\n";
    std::cout << "  Doppler range: " << profile.doppler_hz.front() << " to " 
              << profile.doppler_hz.back() << " Hz\n";
    
    if (dry_run) {
        std::cout << "\n[DRY RUN MODE]\n";
    }
    
    // Open device (unless dry run)
    if (!dry_run) {
        int device_count = rtlsdr_get_device_count();
        if (device_count == 0) {
            std::cerr << "Error: No RTL-SDR devices found\n";
            return 1;
        }
        
        if (rtlsdr_open(&g_dev, device_index) < 0) {
            std::cerr << "Error: Failed to open RTL-SDR device\n";
            return 1;
        }
        
        // Initial frequency
        uint32_t initial_freq = static_cast<uint32_t>(profile.center_freq_hz + profile.doppler_hz.front());
        rtlsdr_set_center_freq(g_dev, initial_freq);
        
        std::cout << "Device opened, initial frequency: " << initial_freq / 1e6 << " MHz\n";
    }
    
    // Install signal handlers
    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);
    
    // Tracking loop
    std::cout << "\nStarting Doppler tracking...\n";
    std::cout << "Press Ctrl+C to stop\n\n";
    
    auto start_time = std::chrono::steady_clock::now();
    double duration = profile.getDuration();
    double last_doppler = 0;
    uint32_t last_freq = 0;
    
    while (g_running) {
        auto now = std::chrono::steady_clock::now();
        double elapsed = std::chrono::duration<double>(now - start_time).count();
        
        // Check if pass is complete
        if (elapsed > duration) {
            std::cout << "\nPass complete.\n";
            break;
        }
        
        // Get current Doppler shift
        double doppler = profile.getDoppler(elapsed);
        
        // Calculate corrected frequency
        uint32_t corrected_freq = static_cast<uint32_t>(profile.center_freq_hz + doppler);
        
        // Only update if frequency changed significantly (>10 Hz)
        if (std::abs(doppler - last_doppler) > 10 || last_freq == 0) {
            if (!dry_run && g_dev) {
                rtlsdr_set_center_freq(g_dev, corrected_freq);
            }
            
            std::cout << "\r[" << std::fixed << std::setprecision(1) << elapsed << "s] "
                      << "Doppler: " << std::setw(7) << std::setprecision(1) << doppler << " Hz, "
                      << "Freq: " << std::setprecision(6) << corrected_freq / 1e6 << " MHz"
                      << "     " << std::flush;
            
            last_doppler = doppler;
            last_freq = corrected_freq;
        }
        
        std::this_thread::sleep_for(std::chrono::milliseconds(update_interval_ms));
    }
    
    std::cout << std::endl;
    
    // Cleanup
    if (g_dev) {
        rtlsdr_close(g_dev);
    }
    
    std::cout << "Doppler tracking complete.\n";
    return 0;
}
