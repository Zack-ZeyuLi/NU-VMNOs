# Verizon(M) & Visible(V1) & Twigby(V2)
## Atlanta
### Location 4 DL
#### Run 1, isolated running
![L4R1R2I](Verizon_images/L4R1R2_MvsV1_IsolatedRunning.png)
Verizon - mmWave dead
![L4R1R2I](Verizon_images/L4R1R2_MvsV1_IR_MAC.png)

#### Run 1, simultaneously running
![L4R1R2S](Verizon_images/L4R1R2_MvsV1_simRunning.png)
Two operators share mmWave well
![L4R1S](Verizon_images/L4R1_MvsV1_SR_MAC.png)
![L4R2S](Verizon_images/L4R2_MvsV1_SR_MAC.png)

### Location 5 DL
Special scheduling pattern when Verizon connected to PCI 728
![L5R4I](Verizon_images/L5R4_MvsV1_IR_MAC.png)
Here was a handover event, the special pattern only shows in PCI 728
![L5R1I](Verizon_images/L5R1_M_IR.png)

### Location 5 UL
#### Run 1, Verizon(pci 728, bw 100) vs Visible(pci 887, bw 10)
728 has worse channel than 887, which lead to fewer RBs
![ULL5R1SR](Verizon_images/UL_L5R1_SR.png)
#### Run 3, Verizon(pci 887, bw 10) vs Visible(pci 887, bw 10)
Visible uses more aggressive scheduling algorithm, which causes higher MCS and higher QAM
![ULL5R2SR](Verizon_images/UL_L5R2_SR.png)
