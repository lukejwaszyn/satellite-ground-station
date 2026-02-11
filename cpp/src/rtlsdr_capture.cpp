/*
 * rtlsdr_capture.cpp
 * Satellite Ground Station - Real-time I/Q Capture
 *
 * High-performance capture with:
 * - Asynchronous I/Q streaming
 * - Ring buffer to prevent drops
 * - Binary output for maximum throughput
 *
 * Author: Luke Waszyn
 * Date: February 2026
 */

#include <rtl-sdr.h>
#include <iostream>
#include <fstream>
#include <vector>
#include <queue>
#include <mutex>
#include <thread>
#include <condition_variable>
#include <atomic>
#include <chrono>
#include <cstring>
#include <csignal>
#include <getopt.h>

// Default configuration
#define DEFAULT_FREQ        137100000   // 137.1 MHz (NOAA-19)
#define DEFAULT_SAMPLE_RATE 2400000     // 2.4 MS/s
#define DEFAULT_GAIN        400         // 40.0 dB (gain is in tenths)
#define DEFAULT_DURATION    900         // 15 minutes
#define BUFFER_SIZE         (16 * 16384) // 256KB per buffer
#define NUM_BUFFERS         16          // Ring buffer depth

// Global state
static std::atomic<bool> g_running(true);
static rtlsdr_dev_t *g_dev = nullptr;

// Thread-safe queue for I/Q buffers
class BufferQueue {
public:
    void push(std::vector<uint8_t>&& buf) {
        std::lock_guard<std::mutex> lock(mutex_);
        queue_.push(std::move(buf));
        cv_.notify_one();
    }
    
    bool pop(std::vector<uint8_t>& buf, int timeout_ms = 1000) {
        std::unique_lock<std::mutex> lock(mutex_);
        if (cv_.wait_for(lock, std::chrono::milliseconds(timeout_ms),
                         [this] { return !queue_.empty(); })) {
            buf = std::move(queue_.front());
            queue_.pop();
            return true;
        }
        return false;
    }
    
    size_t size() {
        std::lock_guard<std::mutex> lock(mutex_);
        return queue_.size();
    }
    
private:
    std::queue<std::vector<uint8_t>> queue_;
    std::mutex mutex_;
    std::condition_variable cv_;
};

static BufferQueue g_buffer_queue;
static std::atomic<uint64_t> g_samples_captured(0);
static std::atomic<uint64_t> g_bytes_written(0);
static std::atomic<int> g_overflows(0);

// Signal handler
void signal_handler(int signum) {
    std::cerr << "\nSignal " << signum << " received, stopping capture..." << std::endl;
    g_running = false;
}

// RTL-SDR async callback
void rtlsdr_callback(unsigned char *buf, uint32_t len, void *ctx) {
    if (!g_running) {
        rtlsdr_cancel_async(g_dev);
        return;
    }
    
    // Copy to vector and push to queue
    std::vector<uint8_t> buffer(buf, buf + len);
    g_buffer_queue.push(std::move(buffer));
    
    g_samples_captured += len / 2;  // 2 bytes per sample (I + Q)
    
    // Check for queue overflow
    if (g_buffer_queue.size() > NUM_BUFFERS) {
        g_overflows++;
    }
}

// Writer thread
void writer_thread(const std::string& filename) {
    std::ofstream outfile(filename, std::ios::binary);
    if (!outfile) {
        std::cerr << "Error: Cannot open output file: " << filename << std::endl;
        g_running = false;
        return;
    }
    
    std::vector<uint8_t> buffer;
    
    while (g_running || g_buffer_queue.size() > 0) {
        if (g_buffer_queue.pop(buffer, 100)) {
            outfile.write(reinterpret_cast<char*>(buffer.data()), buffer.size());
            g_bytes_written += buffer.size();
        }
    }
    
    outfile.close();
}

// Progress display thread
void progress_thread(uint32_t sample_rate, int duration_sec) {
    auto start_time = std::chrono::steady_clock::now();
    uint64_t expected_samples = static_cast<uint64_t>(sample_rate) * duration_sec;
    
    while (g_running) {
        std::this_thread::sleep_for(std::chrono::seconds(1));
        
        auto now = std::chrono::steady_clock::now();
        auto elapsed = std::chrono::duration_cast<std::chrono::seconds>(now - start_time).count();
        
        double progress = static_cast<double>(g_samples_captured) / expected_samples * 100.0;
        double mb_written = g_bytes_written / 1e6;
        double rate = mb_written / (elapsed > 0 ? elapsed : 1);
        
        std::cout << "\r[" << elapsed << "s] "
                  << g_samples_captured / 1000000 << "M samples, "
                  << std::fixed << std::setprecision(1)
                  << mb_written << " MB written ("
                  << rate << " MB/s), "
                  << "Queue: " << g_buffer_queue.size() << ", "
                  << "Overflows: " << g_overflows
                  << "     " << std::flush;
    }
    std::cout << std::endl;
}

void print_usage(const char* progname) {
    std::cout << "Usage: " << progname << " [options] -o <output_file>\n"
              << "\nOptions:\n"
              << "  -f <freq>      Center frequency in Hz (default: " << DEFAULT_FREQ << ")\n"
              << "  -s <rate>      Sample rate in Hz (default: " << DEFAULT_SAMPLE_RATE << ")\n"
              << "  -g <gain>      Gain in dB (default: " << DEFAULT_GAIN/10.0 << ")\n"
              << "  -d <duration>  Capture duration in seconds (default: " << DEFAULT_DURATION << ")\n"
              << "  -o <file>      Output file (required)\n"
              << "  -D <device>    Device index (default: 0)\n"
              << "  -h             Show this help\n"
              << "\nExample:\n"
              << "  " << progname << " -f 137100000 -s 2400000 -g 40 -d 900 -o capture.bin\n";
}

int main(int argc, char *argv[]) {
    // Configuration
    uint32_t frequency = DEFAULT_FREQ;
    uint32_t sample_rate = DEFAULT_SAMPLE_RATE;
    int gain = DEFAULT_GAIN;
    int duration = DEFAULT_DURATION;
    int device_index = 0;
    std::string output_file;
    
    // Parse arguments
    int opt;
    while ((opt = getopt(argc, argv, "f:s:g:d:o:D:h")) != -1) {
        switch (opt) {
            case 'f':
                frequency = std::stoul(optarg);
                break;
            case 's':
                sample_rate = std::stoul(optarg);
                break;
            case 'g':
                gain = static_cast<int>(std::stof(optarg) * 10);  // Convert dB to tenths
                break;
            case 'd':
                duration = std::stoi(optarg);
                break;
            case 'o':
                output_file = optarg;
                break;
            case 'D':
                device_index = std::stoi(optarg);
                break;
            case 'h':
            default:
                print_usage(argv[0]);
                return (opt == 'h') ? 0 : 1;
        }
    }
    
    if (output_file.empty()) {
        std::cerr << "Error: Output file required (-o)\n";
        print_usage(argv[0]);
        return 1;
    }
    
    // Install signal handlers
    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);
    
    // Open device
    int device_count = rtlsdr_get_device_count();
    if (device_count == 0) {
        std::cerr << "Error: No RTL-SDR devices found\n";
        return 1;
    }
    
    std::cout << "Found " << device_count << " RTL-SDR device(s)\n";
    std::cout << "Using device " << device_index << ": " 
              << rtlsdr_get_device_name(device_index) << "\n";
    
    if (rtlsdr_open(&g_dev, device_index) < 0) {
        std::cerr << "Error: Failed to open RTL-SDR device\n";
        return 1;
    }
    
    // Configure device
    std::cout << "\nConfiguration:\n";
    std::cout << "  Frequency:   " << frequency / 1e6 << " MHz\n";
    std::cout << "  Sample rate: " << sample_rate / 1e6 << " MS/s\n";
    std::cout << "  Gain:        " << gain / 10.0 << " dB\n";
    std::cout << "  Duration:    " << duration << " seconds\n";
    std::cout << "  Output:      " << output_file << "\n";
    
    rtlsdr_set_sample_rate(g_dev, sample_rate);
    rtlsdr_set_center_freq(g_dev, frequency);
    rtlsdr_set_tuner_gain_mode(g_dev, 1);  // Manual gain
    rtlsdr_set_tuner_gain(g_dev, gain);
    rtlsdr_reset_buffer(g_dev);
    
    // Verify settings
    std::cout << "\nActual settings:\n";
    std::cout << "  Frequency:   " << rtlsdr_get_center_freq(g_dev) / 1e6 << " MHz\n";
    std::cout << "  Sample rate: " << rtlsdr_get_sample_rate(g_dev) / 1e6 << " MS/s\n";
    std::cout << "  Gain:        " << rtlsdr_get_tuner_gain(g_dev) / 10.0 << " dB\n";
    
    // Start threads
    std::cout << "\nStarting capture...\n";
    std::thread writer(writer_thread, output_file);
    std::thread progress(progress_thread, sample_rate, duration);
    
    // Set up duration timer
    std::thread timer([duration]() {
        std::this_thread::sleep_for(std::chrono::seconds(duration));
        g_running = false;
    });
    timer.detach();
    
    // Start async read (blocks until cancelled)
    rtlsdr_read_async(g_dev, rtlsdr_callback, nullptr, NUM_BUFFERS, BUFFER_SIZE);
    
    // Wait for writer to finish
    g_running = false;
    writer.join();
    progress.join();
    
    // Cleanup
    rtlsdr_close(g_dev);
    
    // Summary
    std::cout << "\n========================================\n";
    std::cout << "Capture complete!\n";
    std::cout << "  Samples:   " << g_samples_captured << "\n";
    std::cout << "  Written:   " << g_bytes_written / 1e6 << " MB\n";
    std::cout << "  Overflows: " << g_overflows << "\n";
    std::cout << "  Output:    " << output_file << "\n";
    std::cout << "========================================\n";
    
    return 0;
}
