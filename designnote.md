# Design Notes

## 1. WDM Concept

A physical fiber can carry multiple optical wavelength channels simultaneously.

- Fiber: physical transmission medium
- Wavelength channel: one optical carrier inside the fiber
- Each channel carries either 10 Gb/s or 40 Gb/s OOK traffic in this project.

## 2. Traffic Routing

The physical topology is:

A -- 320 km -- B -- 400 km -- C
                |
              180 km
                |
                D

B is the central optical routing node.

## 3. Wavelength Routing at Node B

For a wavelength arriving at B:

- DROP: traffic terminates at B.
- PASS: transit traffic remains in the optical domain and continues to another link.
- ADD: traffic generated locally at B is inserted into an outgoing fiber.

Transit traffic is assumed to satisfy wavelength continuity, i.e. it keeps the same wavelength across B.

## 4. Wavelength Reuse

The same wavelength may be reused on different fibers as long as the channels do not coexist on the same physical fiber.

Example:

A -> B may use λ1 for A-to-B traffic.
B -> C may independently reuse λ1 for B-to-C traffic.

This does not constitute wavelength conversion.