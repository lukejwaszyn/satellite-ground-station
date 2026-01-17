# Risk Register

## Risk Assessment Matrix

| Risk ID | Risk Description | Probability | Impact | Severity | Mitigation Strategy | Contingency Plan |
|---------|-----------------|-------------|---------|----------|--------------------|--------------------|
| R-001 | LNA PCB fabrication delay | Medium | High | **HIGH** | Order early (Week 3), 3-day turnaround | Proceed to V3 without LNA |
| R-002 | Poor weather during test passes | High | Low | **MEDIUM** | Monitor forecast, prioritize clear days | Delay 1-2 days, 2x daily pass opportunities |
| R-003 | C++ real-time performance insufficient | Medium | Medium | **MEDIUM** | Prototype in Python, optimize critical loops | Fall back to Python for V4 demo |
| R-004 | RTL-SDR USB bandwidth saturation | Low | Medium | **LOW** | Use 250 kHz sample rate (proven sufficient) | Reduce sample rate further if needed |
| R-005 | Coursework intensifies (semester ramp-up) | High | High | **HIGH** | Front-load Weeks 1-3, document early | V3 minimum viable, extend V4-V5 into March |
| R-006 | Antenna VSWR higher than expected | Medium | Medium | **MEDIUM** | Measure on VNA before deployment | Trim/rebuild antenna if needed |
| R-007 | LNA oscillation or instability | Medium | High | **HIGH** | Follow proven design, test on bench first | Add isolation, reduce gain if necessary |
| R-008 | Low SNR prevents decode | Low | High | **MEDIUM** | LNA boosts signal, target high-elevation passes | Accept lower quality for V3, iterate |
| R-009 | Doppler calculation error | Low | Medium | **LOW** | Validate against Heavens-Above (V0) | Refine SGP4 implementation, check TLE freshness |
| R-010 | Disk space exhaustion | Low | Low | **LOW** | Monitor usage, 500 MB per pass budget | Delete old I/Q files after decode |

**Severity Levels:**
- **HIGH:** Could block project completion or major milestone
- **MEDIUM:** Could delay project or degrade performance
- **LOW:** Minor impact, easily worked around

---

## R-001: LNA PCB Fabrication Delay

**Description:**  
PCB fabrication takes 3-5 days. If ordered late in Week 3 or issues arise (design error, fab house delay, shipping), LNA may not arrive until Week 5, blocking V2 verification.

**Probability:** Medium (30-50%)  
**Impact:** High (blocks V2, delays V3-V4)

**Root Causes:**
- Late PCB order submission
- Design errors discovered after fabrication
- Fabrication house backlog or delays
- Shipping delays

**Mitigation Strategy:**
1. Complete LNA schematic and layout early in Week 3 (Day 1-2)
2. Conduct thorough design review before submitting (check DRC, verify footprints)
3. Select fabrication option with 3-day turnaround (may cost extra, but worth it)
4. Order components in parallel with PCB fab (Mouser/Digikey expedited shipping)
5. Have backup plan ready before Week 3 ends

**Contingency Plan:**
- **If LNA delayed to Week 5:** Proceed directly to V3 without LNA
  - Accept lower SNR and noisier images for initial decode
  - Integrate LNA post-V3 as performance improvement, not blocker
  - V3 pass criteria adjusted: SNR >5 dB instead of >10 dB
- **If LNA fails completely:** System still functional, just reduced sensitivity
  - Document as limitation, not failure
  - Focus on high-elevation passes (>40°) for best chance of decode

**Early Warning Indicators:**
- Week 3 Day 3: If PCB not ordered yet → escalate priority
- Week 3 Day 5: If PCB order confirmed but no tracking info → contact fab house
- Week 4 Day 2: If PCB not received → activate contingency (proceed without LNA)

**Owner:** Primary project owner (you)  
**Status:** Monitoring (not yet triggered)

---

## R-002: Poor Weather During Test Passes

**Description:**  
Cloud cover, precipitation, or storms during scheduled satellite passes could degrade RF signal quality or make outdoor antenna deployment impractical.

**Probability:** High (60-80% in PA winter)  
**Impact:** Low (minor delays, multiple opportunities)

**Root Causes:**
- Winter weather in State College, PA (snow, rain, clouds)
- Limited control over timing (satellites pass on fixed schedule)

**Mitigation Strategy:**
1. Monitor weather forecast 24-48 hours in advance
2. Prioritize clear-sky passes for V1, V2, V3 testing
3. Accept that some captures will be lower quality due to weather
4. Use weather as a test variable (compare clear vs. cloudy passes in V5)

**Contingency Plan:**
- NOAA satellites pass 2x per day → if one pass has poor weather, try next pass (12 hours later)
- Acceptable to delay verification stage by 1-2 days for better conditions
- For V5, weather variability actually helps characterize system performance under real-world conditions

**Impact on Timeline:**
- V1, V2, V3: May add 1-2 day delay per stage (acceptable buffer in 7-week timeline)
- V4, V5: Weather less critical (automated testing can run regardless)

**Early Warning Indicators:**
- Check weather forecast daily starting in Week 2
- If forecast shows extended bad weather (>3 days), consider alternative indoor RF test (use signal generator)

**Owner:** Primary project owner  
**Status:** Accepted risk (part of real-world RF testing)

---

## R-003: C++ Real-Time Performance Insufficient

**Description:**  
C++ capture program may not achieve required real-time performance due to coding issues, library limitations, or platform constraints (macOS vs. Linux differences).

**Probability:** Medium (30-50%)  
**Impact:** Medium (delays V4, but V3 still functional)

**Root Causes:**
- Insufficient C++ optimization
- librtlsdr library quirks on macOS
- USB bandwidth or latency issues
- CPU too slow for real-time DSP (unlikely on M4, but possible)

**Mitigation Strategy:**
1. Prototype core functionality in Python first (Week 5)
2. Profile Python code to identify performance bottlenecks
3. Port only critical real-time loops to C++ (not entire system)
4. Use proven libraries (librtlsdr has mature C++ examples)
5. Test early in Week 6, leave time for debugging

**Contingency Plan:**
- **If C++ too slow:** Use Python for V4 demonstration
  - Still qualifies as "real-time Doppler tracking" even if Python (just slower)
  - Document as "future work: optimize with C++ for true real-time"
  - Image quality still improves with automated Doppler correction
- **If neither Python nor C++ work:** Fall back to manual Doppler (as in V3)
  - V4 becomes "demonstrate improved manual Doppler workflow" instead of full automation
  - System still functional, just less autonomous

**Performance Targets:**
- Minimum viable: 250 kHz I/Q capture without drops
- Preferred: <100 ms latency for Doppler updates
- Acceptable fallback: Python with 1-second latency (still better than manual)

**Early Warning Indicators:**
- Week 6 Day 2: If C++ prototype not capturing reliably → pivot to Python
- Week 6 Day 4: If Python not meeting performance → adjust V4 scope

**Owner:** Primary project owner  
**Status:** Monitoring (mitigation in progress)

---

## R-004: RTL-SDR USB Bandwidth Saturation

**Description:**  
RTL-SDR at 2.4 MS/s generates ~19 MB/s data rate. USB 2.0 limits may cause sample drops, especially if other USB devices active or poor cable quality.

**Probability:** Low (10-20%)  
**Impact:** Medium (corrupted I/Q, decode failures)

**Root Causes:**
- USB 2.0 bandwidth limit (~35 MB/s theoretical, ~20 MB/s practical)
- USB hub contention (other devices on same bus)
- Poor quality or long USB cable
- Inefficient driver or OS issues

**Mitigation Strategy:**
1. Use 250 kHz output sample rate (decimated from 2.4 MS/s in RTL-SDR)
  - 250 kHz = ~2 MB/s → well within USB 2.0 limits
2. Connect RTL-SDR directly to laptop USB port (not through hub)
3. Use high-quality, short USB cable
4. Close unnecessary USB devices during capture
5. Monitor for sample drops in logs

**Contingency Plan:**
- **If drops detected:** Further reduce sample rate to 200 kHz or 180 kHz
  - APT bandwidth is ~17 kHz, so 180 kHz still provides adequate Nyquist margin
- **If persistent issues:** Test on backup laptop (ROG G14) with different USB controller
- **If hardware limitation:** Purchase higher-performance SDR (HackRF, Airspy) – not preferred but available

**Monitoring:**
- Log sample drop events
- Check I/Q file size consistency (should match expected size for duration)
- Review spectrograms for gaps or discontinuities

**Early Warning Indicators:**
- V1: If capture shows missing samples → investigate immediately
- V3: If decode shows artifacts → check for sample drops in logs

**Owner:** Primary project owner  
**Status:** Low priority (proven design, unlikely to trigger)

---

## R-005: Coursework Intensifies (Semester Ramp-Up)

**Description:**  
Project planned for Weeks 1-7 of spring semester. Academic workload typically increases significantly after Week 3-4 (midterms, projects, exams).

**Probability:** High (80-100%)  
**Impact:** High (reduced time for project, may miss V4-V5)

**Root Causes:**
- Predictable semester cycle (courses intensify mid-semester)
- Competing deadlines (exams, homework, other projects)
- Unexpected academic challenges (difficult assignments, group projects)

**Mitigation Strategy:**
1. **Front-load critical work:**
  - Weeks 1-3: Requirements, architecture, V0, antenna design, LNA design
  - These are foundational and must be completed early
2. **Establish documentation early:**
  - Complete all requirements and architecture docs in Week 1 (TODAY)
  - Reduces re-work and context switching later
3. **Define minimum viable project:**
  - V3 (first decoded image) is sufficient for portfolio and applications
  - V4-V5 are "stretch goals" that enhance but don't define success
4. **Protect weekends:**
  - Reserve Saturdays for satellite project work if weekday time constrained

**Contingency Plan:**
- **If time-constrained after Week 5:**
  - V3 (first decode) is minimum viable project → sufficient for JPL/SpaceX applications
  - V4-V5 can extend into March (Week 8-10) with reduced scope
  - Accept that "in progress" is valid for application purposes
- **If severe time crunch:**
  - Focus only on V3 completion
  - Document V4-V5 as "future work" in final report
  - Still demonstrates systems engineering approach and technical depth

**Success Metrics (Adjusted for Risk):**
- **Minimum viable:** V0-V3 complete (working decoder, one good image)
- **Target:** V0-V4 complete (automated system)
- **Stretch goal:** V0-V5 complete (full characterization)

**Early Warning Indicators:**
- Week 4: If coursework consuming >30 hours/week → activate contingency
- Week 5: If falling behind on project timeline → reassess V4-V5 scope

**Owner:** Primary project owner  
**Status:** High probability, mitigation in progress (front-loading work)

---

## R-006: Antenna VSWR Higher Than Expected

**Description:**  
Custom dipole antenna may not resonate at 137 MHz as designed due to fabrication errors, environmental coupling, or calculation mistakes.

**Probability:** Medium (30-40%)  
**Impact:** Medium (reduces efficiency, lowers SNR)

**Root Causes:**
- Length calculation error (assumes free-space, real-world has coupling effects)
- Coax feed point impedance mismatch
- Proximity to metal objects (mounts, buildings) detunes antenna
- Material properties differ from design assumptions

**Mitigation Strategy:**
1. Measure VSWR on VNA before deployment (Week 2)
2. If VSWR >2:1, trim antenna elements iteratively
3. Document measured resonance and adjust length accordingly
4. Test in deployment location to account for environmental effects

**Contingency Plan:**
- **If VSWR 2-3:1:** Acceptable for initial testing, proceed with V1
  - Some loss in efficiency, but signal should still be detectable
  - Can optimize post-V1 if needed
- **If VSWR >3:1:** Rebuild antenna with corrected length
  - Use measured VSWR data to calculate new length
  - One rebuild iteration adds 1-2 days to timeline (acceptable)
- **Worst case:** Use stock RTL-SDR antenna for V1 (known to work, but suboptimal)

**Performance Impact:**
- VSWR 1.5:1 → ~96% power transfer (excellent)
- VSWR 2:1 → ~89% power transfer (acceptable)
- VSWR 3:1 → ~75% power transfer (degraded but functional)

**Early Warning Indicators:**
- Week 2: VNA measurement shows VSWR >2:1 → trigger optimization
- V1: If no carrier detected → check antenna as first troubleshooting step

**Owner:** Primary project owner  
**Status:** Monitoring (will measure in Week 2)

---

## R-007: LNA Oscillation or Instability

**Description:**  
LNA circuit may oscillate due to insufficient stability margin, poor grounding, or layout issues, rendering it unusable.

**Probability:** Medium (20-30%)  
**Impact:** High (blocks V2, must redesign)

**Root Causes:**
- Insufficient decoupling capacitors
- Ground loops in PCB layout
- Positive feedback path (input/output coupling)
- Bias network instability
- Active device selected has poor stability factor

**Mitigation Strategy:**
1. Use proven LNA topology (common-emitter or common-source with stability resistors)
2. Follow RF PCB layout best practices:
  - Solid ground plane
  - Via stitching around RF traces
  - Short signal paths
  - Input/output isolation (physical separation)
3. Calculate stability factor (K > 1) during design phase
4. Include series resistors for unconditional stability if needed (trades gain for stability)
5. Bench test before integration:
  - Apply power, check for oscillation with spectrum analyzer
  - Measure bias voltage and current
  - Check for thermal runaway (overheating)

**Contingency Plan:**
- **If unstable on first power-up:**
  - Add ferrite bead or isolation resistor at input/output
  - Reduce gain by adding series resistance (e.g., 10Ω at input)
  - Check for ground loops, improve layout if possible
- **If severe oscillation:**
  - Redesign PCB with improved layout → 3-5 day delay
  - Fall back to commercial LNA module (e.g., Nooelec SAWbird) → costs $40-50 but guaranteed to work
- **If no time for redesign:**
  - Proceed without LNA (as in R-001 contingency)

**Design Review Checklist:**
- [ ] Stability factor K > 1.5 across 100-200 MHz
- [ ] Decoupling capacitors at power pins (100 nF + 10 µF)
- [ ] Via stitching around RF traces
- [ ] Input/output physical separation >10 mm
- [ ] Bias network checked for stability

**Early Warning Indicators:**
- Week 4: If LNA heats up immediately on power → likely oscillating
- Week 4: If spectrum analyzer shows spurious tones → likely unstable

**Owner:** Primary project owner  
**Status:** Design phase (will test in Week 4)

---

## R-008: Low SNR Prevents Decode

**Description:**  
Even with LNA, signal SNR may be insufficient for reliable APT decode due to environmental factors (RF interference, multipath, weak satellite signal).

**Probability:** Low (10-20%)  
**Impact:** High (blocks V3, must iterate on RF design)

**Root Causes:**
- Urban RF interference (FM broadcast, cell towers, WiFi)
- Multipath fading (reflections from buildings)
- Satellite transmitter power lower than expected (older satellites degrade over time)
- Antenna pattern null in direction of satellite
- LNA noise figure higher than designed

**Mitigation Strategy:**
1. Target high-elevation passes (>40°) for initial V3 attempt
  - Higher elevation = stronger signal, less atmospheric attenuation
2. Deploy antenna in clear RF environment (away from buildings, power lines)
3. Use spectral analysis in V1 to identify interference sources
4. Time captures to avoid known interference (e.g., avoid rush hour if cell tower nearby)
5. Ensure LNA provides expected gain and noise figure (V2 validation)

**Contingency Plan:**
- **If SNR 5-10 dB:** Decode may be noisy but functional
  - Accept lower quality for V3 demonstration
  - Document as environmental limitation
  - Iterate on RF chain (better antenna, higher gain LNA) post-V3
- **If SNR <5 dB:** Decode unlikely to succeed
  - Troubleshoot systematically:
    1. Check antenna connection (SMA tight, no damage)
    2. Verify LNA powered and functional
    3. Check for local interference sources
    4. Try different satellite or pass
  - If persistent: Consider commercial LNA upgrade or better antenna location
- **If all else fails:** Use simulated I/Q file to demonstrate decode algorithm works
  - Not ideal, but proves software capability even if RF chain limited

**Success Threshold:**
- V3 target: SNR >10 dB (clean decode)
- V3 acceptable: SNR >5 dB (noisy but recognizable image)
- V3 minimum: Sync pulses detected, even if image quality poor

**Early Warning Indicators:**
- V1: If SNR <3 dB on high-elevation pass → investigate RF chain
- V2: If LNA doesn't improve SNR by expected amount → check LNA functionality

**Owner:** Primary project owner  
**Status:** Low priority (LNA should provide adequate margin)

---

## R-009: Doppler Calculation Error

**Description:**  
SGP4 propagation or Doppler calculation may contain errors, causing frequency offset mismatch between predicted and actual carrier.

**Probability:** Low (5-10%)  
**Impact:** Medium (degrades V1 results, complicates V4)

**Root Causes:**
- Bug in Doppler calculation code
- TLE data stale or incorrect
- Incorrect observer location coordinates
- Clock synchronization error (system time off by minutes)

**Mitigation Strategy:**
1. Validate Doppler calculation in V0 (compare to reference tools)
2. Use fresh TLE data (updated within 24 hours)
3. Verify observer location coordinates (State College, PA)
4. Ensure system clock synchronized (NTP)
5. Cross-check predictions against Heavens-Above

**Contingency Plan:**
- **If Doppler error detected in V1:**
  - Measure actual carrier frequency vs. predicted
  - Calculate correction factor
  - Apply correction to future predictions
- **If systematic error:**
  - Debug Doppler calculation code
  - Verify SGP4 implementation (Skyfield is proven, but check usage)
- **If unable to resolve:**
  - Capture at nominal frequency (137.X MHz) without Doppler correction
  - Accept wider capture bandwidth to include full Doppler range

**Validation Method:**
- V1: Measure carrier peak in PSD, compare to predicted frequency
- Acceptable error: ±2 kHz (well within APT bandwidth)
- If error >5 kHz: investigate and correct

**Early Warning Indicators:**
- V0: If predictions don't match Heavens-Above → investigate immediately
- V1: If carrier not at predicted frequency → check Doppler calculation

**Owner:** Primary project owner  
**Status:** Low priority (V0 validated successfully)

---

## R-010: Disk Space Exhaustion

**Description:**  
Raw I/Q files (~300-500 MB each) could fill disk if many captures stored without cleanup.

**Probability:** Low (10-20%)  
**Impact:** Low (prevents new captures, but easily resolved)

**Root Causes:**
- Insufficient disk space monitoring
- Many captures without deletion of old files
- Larger I/Q files than expected (longer passes, higher sample rate)

**Mitigation Strategy:**
1. Budget 500 MB per pass × 10-15 passes = ~7.5 GB total
2. Check available disk space before starting V5 (multi-pass testing)
3. Delete raw I/Q files after successful decode (keep only decoded images)
4. Compress old I/Q files (gzip can reduce by ~50%)
5. Monitor disk usage with automated script

**Contingency Plan:**
- **If disk fills during V5:**
  - Delete oldest raw I/Q files (keep decoded images and metadata)
  - Compress remaining I/Q files
  - Move data to external storage or cloud backup
- **If persistent issue:**
  - Reduce capture duration (start later, end earlier)
  - Reduce sample rate (250 kHz → 200 kHz saves 20%)

**Monitoring:**
- Check disk space daily during V5
- Automated alert if free space <5 GB

**Early Warning Indicators:**
- Week 6: If disk space <10 GB before V5 → clean up old data
- V5 Day 2: If disk space declining rapidly → implement cleanup strategy

**Owner:** Primary project owner  
**Status:** Low priority (laptop has adequate storage, easy to resolve)

---

## Risk Summary Dashboard

| Risk ID | Severity | Status | Owner | Next Review |
|---------|----------|--------|-------|-------------|
| R-001 | HIGH | Monitoring | You | Week 3 Day 1 |
| R-002 | MEDIUM | Accepted | You | Daily (Week 2+) |
| R-003 | MEDIUM | Monitoring | You | Week 6 Day 1 |
| R-004 | LOW | Monitoring | You | V1 (Week 2) |
| R-005 | HIGH | Mitigation Active | You | Weekly |
| R-006 | MEDIUM | Monitoring | You | Week 2 VNA test |
| R-007 | HIGH | Design Phase | You | Week 4 bench test |
| R-008 | MEDIUM | Monitoring | You | V1 (Week 2) |
| R-009 | LOW | Monitoring | You | V1 (Week 2) |
| R-010 | LOW | Monitoring | You | Week 6 |

**Overall Risk Posture:** MODERATE  
**Critical Risks:** R-001 (LNA delay), R-005 (coursework), R-007 (LNA instability)  
**Mitigation Status:** Active mitigation in progress for high-severity risks

---

## Risk Review Schedule

- **Weekly:** Review all HIGH risks, update status
- **Before each verification stage:** Review risks relevant to that stage
- **After any risk triggers:** Update contingency plan status, document lessons learned

**Next Scheduled Review:** End of Week 1 (after requirements/architecture complete)
