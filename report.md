# Design and Analysis of a Four-Node Long-Haul WDM Optical Network
## Project Overview
## Network Configuration
The network consists of four nodes representing four cities. Node B serves as the central node. Each pair of adjacent nodes is connected by a pair of optical fibers, with one fiber used for each transmission direction.

The physical link distances are 320 km between A and B, 400 km between B and C, and 180 km between B and D, as shown in the following figure.

<!-- Insert network topology figure here -->
A ----320 km---- B ----400 km---- C
                  |
                180 km
                  |
                  D

## Design Requirements and Constractions
### Constractions
The optical network was designed under the following system, component, and physical-layer constraints.

| Category | Parameter / Constraint | Requirement |
| --- | --- | --- |
| Channel | Modulation format | OOK |
| Channel | Data rate | Each wavelength channel carries either 10 Gb/s or 40 Gb/s |
| Transmitter | Laser type | Each wavelength channel uses a DFB laser |
| Transmitter | Modulator type | Each wavelength channel uses a LiNbO₃-based external modulator |
| Transmitter | Modulator bandwidth | 10 GHz or 40 GHz |
| Transmitter | Launch power | ≤ 2 mW (3 dBm) per channel |
| Receiver | Receiver type | Each wavelength channel uses either a PIN photodiode or a balanced detector with a local oscillator |
| Receiver | Received optical power | ≤ 0.5 mW per channel |
| Amplifier | Amplifier type | Optical amplifiers may be used when required |
| Amplifier | Placement | Amplifiers may only be placed at the specified sites where electrical power is available |
| Amplifier | Maximum gain | ≤ 20 dB |
| Amplifier | Output power | ≤ 5 mW (7 dBm) per channel after amplification |
| Link Performance | Receiver SNR | ≥ 13 dB |
| Link Performance | Nonlinear phase shift | Total nonlinear phase shift due to SPM must be < π rad |
| Routing | Traffic routing | Traffic demands must be mapped to the appropriate physical paths through the network |
| Routing | Central node B | Transit traffic must be wavelength-routed in the optical domain without electrical conversion or data regeneration |
| WDM | Add/drop operation | Relevant wavelength channels must be dropped at their destination and new local channels added where required |
| Physical-Layer Analysis | Power | Optical power must be analyzed along each link |
| Physical-Layer Analysis | Noise / SNR | Receiver SNR must be analyzed for each link |
| Physical-Layer Analysis | Chromatic dispersion | Dispersion must be evaluated for each link |
| Physical-Layer Analysis | Fiber nonlinearity | Fiber nonlinear effects, including SPM, must be evaluated |
| Components | Commercial availability | All major optical components must correspond to commercially available products |
| Components | Component specifications | Relevant parameters such as insertion loss, gain, bandwidth, wavelength range, and power limits must be included |
| Design | Cost consideration | Excessive or unnecessary component deployment should be avoided |
### Design Assumptions

- 40 Gb/s channels are used whenever possible to reduce the total number of wavelength channels; remaining traffic is carried using 10 Gb/s channels.
- Transit traffic through node B maintains wavelength continuity.
- No wavelength conversion is used at node B.
- The same wavelength may be reused on different physical fibers when no wavelength conflict exists on the same fiber.
## Traffic Routing and Allocation
### Traffic Routing
The network is organized in a tree topology, with a unique physical path between each pair of nodes. Node B serves as the central routing node. Therefore, traffic exchanged between the outer nodes A, C, and D must pass through node B.

The traffic demands are shown in the following matrix.
| Tx \ Rx | A | B | C | D |
| --- | ---: | ---: | ---: | ---: |
| A | 0 | 60 | 50 | 50 |
| B | 70 | 0 | 30 | 20 |
| C | 30 | 50 | 0 | 30 |
| D | 20 | 30 | 60 | 0 |

*All traffic demands are in Gb/s.*<br>
**Traffic Demands and Routes**
| Demand | Data Rate | Route |
| --- | ---: | --- |
| A → B | 60 Gb/s | A-B |
| A → C | 50 Gb/s | A-B-C |
| A → D | 50 Gb/s | A-B-D |
| B → A | 70 Gb/s | B-A |
| B → C | 30 Gb/s | B-C |
| B → D | 20 Gb/s | B-D |
| C → A | 30 Gb/s | C-B-A |
| C → B | 50 Gb/s | C-B |
| C → D | 30 Gb/s | C-B-D |
| D → A | 20 Gb/s | D-B-A |
| D → B | 30 Gb/s | D-B |
| D → C | 60 Gb/s | D-B-C |
### Channel Allocation 
Since only 40 Gb/s and 10 Gb/s OOK channels are available, each traffic demand is divided into one or more wavelength channels. To reduce the total number of channels, simplify the system architecture, and lower the component cost, 40 Gb/s channels are used whenever possible, while the remaining traffic is carried by 10 Gb/s channels.

This allocation results in a total of 32 channel instances across all end-to-end traffic demands. However, these do not require 32 distinct wavelengths, since the same wavelength can be reused on different physical fibers when no wavelength conflict occurs. The following table shows the channel allocation for each traffic demand.
| Demand | Data Rate | Channel Allocation | Number of Channels |
| --- | ---: | --- | ---: |
| A → B | 60 Gb/s | 40 + 10 + 10 | 3 |
| A → C | 50 Gb/s | 40 + 10 | 2 |
| A → D | 50 Gb/s | 40 + 10 | 2 |
| B → A | 70 Gb/s | 40 + 10 + 10 + 10 | 4 |
| B → C | 30 Gb/s | 10 + 10 + 10 | 3 |
| B → D | 20 Gb/s | 10 + 10 | 2 |
| C → A | 30 Gb/s | 10 + 10 + 10 | 3 |
| C → B | 50 Gb/s | 40 + 10 | 2 |
| C → D | 30 Gb/s | 10 + 10 + 10 | 3 |
| D → A | 20 Gb/s | 10 + 10 | 2 |
| D → B | 30 Gb/s | 10 + 10 + 10 | 3 |
| D → C | 60 Gb/s | 40 + 10 + 10 | 3 |
### Logical Wavelength Assignment
The wavelength assignment is designed to use the minimum number of logical wavelength slots while avoiding wavelength conflicts on each directed fiber. The following rules are applied:

- The same wavelength cannot be assigned to multiple independent channels on the same directed fiber.
- The same wavelength can be reused on different physical fibers when no conflict occurs.
- For transit traffic passing through node B, wavelength continuity is maintained. For example, if an A → C channel uses $\lambda_4$ on the A → B link, it continues to use $\lambda_4$ on the B → C link without wavelength conversion.
- $\lambda_1$–$\lambda_9$ are logical wavelength labels. Their physical wavelength values will be determined later according to the selected WDM components.

| Demand | Data Rate | Channel Allocation | Assigned Wavelengths | Route | B Operation |
| --- | ---: | --- | --- | --- | --- |
| A → B | 60 Gb/s | 40 + 10 + 10 | λ1 (40G), λ2 (10G), λ3 (10G) | A-B | DROP |
| A → C | 50 Gb/s | 40 + 10 | λ4 (40G), λ5 (10G) | A-B-C | PASS → C |
| A → D | 50 Gb/s | 40 + 10 | λ6 (40G), λ7 (10G) | A-B-D | PASS → D |
| B → A | 70 Gb/s | 40 + 10 + 10 + 10 | λ6 (40G), λ7 (10G), λ8 (10G), λ9 (10G) | B-A | ADD |
| B → C | 30 Gb/s | 10 + 10 + 10 | λ1 (10G), λ2 (10G), λ3 (10G) | B-C | ADD |
| B → D | 20 Gb/s | 10 + 10 | λ1 (10G), λ2 (10G) | B-D | ADD |
| C → A | 30 Gb/s | 10 + 10 + 10 | λ1 (10G), λ2 (10G), λ3 (10G) | C-B-A | PASS → A |
| C → B | 50 Gb/s | 40 + 10 | λ6 (40G), λ7 (10G) | C-B | DROP |
| C → D | 30 Gb/s | 10 + 10 + 10 | λ4 (10G), λ5 (10G), λ8 (10G) | C-B-D | PASS → D |
| D → A | 20 Gb/s | 10 + 10 | λ4 (10G), λ5 (10G) | D-B-A | PASS → A |
| D → B | 30 Gb/s | 10 + 10 + 10 | λ1 (10G), λ2 (10G), λ3 (10G) | D-B | DROP |
| D → C | 60 Gb/s | 40 + 10 + 10 | λ6 (40G), λ7 (10G), λ8 (10G) | D-B-C | PASS → C |
### Wavelength Routing at Node B
B serves as the central city node.Each wavelength channel arriving at or originating from B is handled using one of the following operations:
- **DROP:** The wavelength channel terminates at node B and is removed from the incoming WDM signal for local reception.
- **ADD:** A wavelength channel carrying traffic generated at node B is inserted into the corresponding outgoing WDM fiber.
- **PASS:** The wavelength channel is transit traffic whose destination is another node. It remains in the optical domain and is routed through node B to the appropriate outgoing fiber.

For PASS traffic, wavelength continuity is maintained across node B in this design, and no wavelength conversion is used.<br>
**Examples**
- A → B: Drop at B
- B → C: Add at B
- A → C: Pass B
### Directed Fiber Channel Load
- Maximum: 9 channels
  
| Directed Fiber Segment | Traffic Carried on This Fiber | Total Data Rate | Number of Wavelength Channels |
| --- | --- | ---: | ---: |
| A → B fiber | A→B, A→C, A→D | 160 Gb/s | 7 |
| B → A fiber | B→A, C→A, D→A | 120 Gb/s | 9 |
| B → C fiber | A→C, B→C, D→C | 140 Gb/s | 8 |
| C → B fiber | C→A, C→B, C→D | 110 Gb/s | 8 |
| B → D fiber | A→D, B→D, C→D | 100 Gb/s | 7 |
| D → B fiber | D→A, D→B, D→C | 110 Gb/s | 8 |
max(7, 9, 8, 8, 7, 8) = 9
The proposed assignment uses nine logical wavelength slots. The B → A fiber carries the largest number of simultaneous channels, requiring nine wavelength slots.
## Component Selection

## Link Analysis

### Power Budget
### SNR and ASE Noise
### Chromatic Dispersion
### Fiber Nonlinearity

## Design Constraints and Validation

## Results

## Repository Structure

## Notice
The current repository reorganizes the original course work into an engineering portfolio project and adds a Python-based numerical implementation for reproducibility, verification, visualization, and further design exploration.

Numerical results that are recalculated or updated in the current repository should be treated as the latest version of the analysis.

