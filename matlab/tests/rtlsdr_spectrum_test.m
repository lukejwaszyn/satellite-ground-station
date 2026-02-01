% rtlsdr_spectrum_test.m
% Luke Waszyn - Satellite Ground Station Project
% Purpose: Verify RTL-SDR can capture RF spectrum via MATLAB
% Test captures FM broadcast band (88-108 MHz) to verify hardware

clear; clc; close all;

% SDR Parameters
fc = 98e6;        % Center at 98 MHz (middle of FM band)
Fs = 2.4e6;       % Sample rate (Hz)
frameLen = 2^16;  % Samples per frame
tCapture = 0.5;   % Capture duration (seconds)

% Create RTL-SDR receiver object
fprintf('Initializing RTL-SDR...\n');
rx = comm.SDRRTLReceiver( ...
    'CenterFrequency', fc, ...
    'SampleRate', Fs, ...
    'SamplesPerFrame', frameLen, ...
    'EnableTunerAGC', true, ...
    'OutputDataType', 'single');

fprintf('RTL-SDR initialized successfully.\n');
fprintf('Center frequency: %.1f MHz\n', fc/1e6);
fprintf('Sample rate: %.1f MS/s\n', Fs/1e6);
fprintf('Capturing %.1f seconds...\n\n', tCapture);

% Capture
nFrames = ceil((tCapture * Fs) / frameLen);
x = complex(zeros(nFrames * frameLen, 1, 'single'));

idx = 1;
for k = 1:nFrames
    [y, len] = rx();
    if len > 0
        x(idx:idx+len-1) = y(1:len);
        idx = idx + len;
    end
end

release(rx);
x = x(1:idx-1);

fprintf('Captured %d samples\n', length(x));

% Remove DC offset
x = x - mean(x);

% Compute PSD
NFFT = 2^15;
[Pxx, f] = pwelch(x, hamming(NFFT), round(0.5*NFFT), NFFT, Fs, 'centered');
pxx_dB = 10*log10(Pxx);

% Plot
figure('Color', 'w');
plot((f + fc)/1e6, pxx_dB, 'LineWidth', 1.5);
grid on;
xlabel('Frequency (MHz)');
ylabel('PSD (dB/Hz)');
title('RTL-SDR Spectrum Test: FM Broadcast Band');
xlim([88 108]);

% Identify peaks (FM stations)
[pks, locs] = findpeaks(pxx_dB, 'MinPeakHeight', max(pxx_dB) - 20, 'MinPeakDistance', 100);
freqs_MHz = (f(locs) + fc) / 1e6;

fprintf('\nDetected FM stations:\n');
for i = 1:min(10, length(freqs_MHz))
    fprintf('  %.1f MHz (%.1f dB/Hz)\n', freqs_MHz(i), pks(i));
end

fprintf('\n RTL-SDR spectrum capture SUCCESSFUL!\n');