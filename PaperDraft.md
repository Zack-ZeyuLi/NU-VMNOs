### Target Conference
IMC 2026 short paper

Submission ddl: April 29th

### Core Idea
We want to study when a VMNO truly competes with its host MNO, and what actually explains the performance gap from the RAN side.

Our work is a measurement study of when VMNO–host competition is actually visible at the UE side, and why CQI-based priority is only a partial explanation.

### Our Argument
The VMNO-HostMNO performance hierarchy is not fixed. CQI explains some cases when using same cell, but the cell selection, RAT mode, and operator specific radio condiguration can also affect the performance.

### Story Line
Host MNO perform better than VMNO because Host has higher scheduling priority: partially ture.

<span style="color: green;">Figure 1 shows the overall performance</span>

Senario 1: Same PCI : CQI correlates higher priority and better throughput.

<span style="color: green;">Figure 2 shows performance under same PCI</span>

Senario 2: Different PCI: No longer competing in the same scheduler context.

<span style="color: green;">Figure 3 shows performance under different PCI</span>

Senario 3: HostMNO sometimes chooses a worse cell.

<span style="color: green;">Figure 4 shows connected PCI distrubution and average throughput per PCI</span>

Senario 4: 5G SA vs 5G NSA: VMNO with 5G NSA defeat HostMNO with 5G SA, which imply more advanced access mode does not always lead to better user-visible performance

<span style="color: green;">Figure 5 shows performance SA vs NSA</span>

Senario 5: Different MCS behavior: Under same channel conditions, the VMNO sometimes gets a much higher MCS index than the host. (Probably different MCS tables or link adaptation policies?)

<span style="color: green;">Figure 6 shows VMNO got higher MCS index and correspondingly higher throughput</span>

### Takeaway
- CQI's action scope is every cell
- Cell selection can be matter
- RAT selection may affect performance
- Link adaptation configuration can be matter

### Discussion
Why we use iperf throughput for statistic? - It stands for the user-visible performance.

Why we use MAC throughput for analysis?? - It reveals link behavior.

Why we think the diffrences are primarily RAN-Driven? - We use same iperf server. All tests have similar RTT. Performances fluctuations align with RAN-specific events.

### Related Work
A First Look at Performance in Mobile Virtual Network Operators (IMC 2014)
<span style="color: green;">Application level performace comparison</span>

An In-depth Study of Commercial MVNO: Measurement and Optimization (MobiSys 2019)
<span style="color: green;">MVNO ecosystem / architecture / optimization</span>

Understanding Operational 5G: A First Measurement Study on Its Coverage, Performance and Energy Consumption (SIGCOMM 2020)

Performance of Cellular Networks on the Wheels (IMC 2023)

<span style="color: green;">Cross-layer measurement framework.</span>

A Peek into 5G NSA vs. SA Control Plane Performance (HotMobile 2025)
<span style="color: green;">5G SA does not always outperform NSA.</span>

### Our novelty
First study of VMNO-HostMNO competition through UE-RAN link layer evidence.