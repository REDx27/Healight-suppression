# Mechanical flap actuator options

Research date: 2026-11-26. Budget: under LKR 1,000 per actuator; approximately
17-50 actuators. Prices below are supplier listings checked today, not quotations,
bulk-stock reservations or measured performance. No order or supplier contact was made.
This is an optional demonstrator study; it does not replace the existing LCD workflow.

## Practical recommendation

Start with two positional SG90 micro servos and two light, centre-balanced flaps.
Each servo drives one flap directly, or through a short link. Set and test two angles
approximately 90 degrees apart. This avoids coupling X/Y stepper mechanisms and avoids
building an angle-feedback controller. Buy positional servos, not 360-degree continuous
rotation versions. Actual travel/endpoints and holding current must be tested per batch.
Power plus a PWM command is required; varying the supply voltage does not select an angle.

The closest device to a pulse-operated 90-degree shutter is a **bistable rotary
solenoid**. Commercial products exist, but this search did not verify a Sri Lankan
stock item below LKR 1,000. Treat it as an alternative to investigate, not a priced BOM.

## Options and local evidence

| Option | Observed price | Motion and mechanism | Assessment |
|---|---:|---|---|
| SG90 positional micro servo | LKR 350, ThingerBits | Angle-controlled shaft; attach a light flap | First budget trial; listed in stock, bulk quantity not established |
| MG90S metal-gear micro servo | LKR 580, Alphatronic | Same basic method, metal gears | Alternative if the tested load benefits from metal gears; page showed 17 in stock, not 50 |
| JF-0530B push/pull solenoid | LKR 980, Tronic | 12 V / 1 A, listed 10 mm linear stroke | Requires a crank/linkage, return mechanism and driver; bare actuator barely fits budget |
| Bistable rotary solenoid | No qualifying local quote verified | Pulse-driven angular switching; selected products provide 90 degrees | Closest direct functional match, procurement/budget unresolved |
| Custom magnet/coil flap | No verified completed-unit cost | Coil and permanent magnet with pivot/stops; potentially latching | A new actuator-development task; reliability, cost and timing unproven |
| Shape-memory wire | No qualifying local quote verified | Heated contraction plus return linkage | Cooling-dependent recovery makes it a weak first choice for repeated tracking |

Retail sources:

- [ThingerBits SG90](https://thingerbits.lk/shop/sg90-9g-micro-servo-motor): live page
  showed LKR 350; the search index showed an older LKR 320. Use the live page price.
- [Alphatronic MG90S](https://alphatronic.lk/product/mg90s-metal-gear-micro-servo-9g/):
  LKR 580; the page showed 17 units available.
- [Tronic JF-0530B](https://tronic.lk/product/jf-0530b-12vdc-1a-5n10mm-pull-push-type-solenoid-switch):
  LKR 980, listed in stock, 12 V / 1 A / 10 mm stroke. This is not a rotary actuator.

## Budget examples

Assume one actuator per **independently controlled flap**, not one per row/column.

| Actuator | 17 units | 50 units |
|---|---:|---:|
| SG90 at LKR 350 | LKR 5,950 | LKR 17,500 |
| MG90S at LKR 580 | LKR 9,860 | LKR 29,000 |
| JF-0530B at LKR 980 | LKR 16,660 | LKR 49,000 |

These totals exclude the MCU, power supply, drivers, wiring, hinges, frame and delivery.
A [PCA9685 board](https://www.atomelectronics.lk/product/pca9685-16ch-servo-motor-driver/)
was listed at LKR 1,100. At 16 PWM channels each, 17 servos need two boards and 50 need
four, adding LKR 2,200 or 4,400 respectively. Thus SG90 plus PWM boards is approximately
LKR 8,150 for 17 flaps or LKR 21,900 for 50, before the other parts. Boards share an
I2C bus with separate addresses; they generate control signals, not motor power.

Use a separate regulated servo power rail and common ground. Size supply and wiring
from measured simultaneous movement/hold/startup current; do not power a 17-50 servo
array through an MCU or laptop USB pin. Keep high-current distribution separate from
signal wiring. No whole-array current or loaded response-time result has been measured.

## Why the cheap solenoid is not automatically simpler

The listed JF-0530B moves linearly. A 90-degree flap still needs a lever/crank, hinge,
stops and return mechanism. Each coil requires a suitable transistor/MOSFET and flyback
protection. Obtain its duty-cycle rating; a product listing does not establish safe
continuous holding time. At its listed current, multiple held coils can create a large
power/heat requirement. A low supply voltage alone does not imply low power.

Manufacturer references support the general actuator distinctions:

- [Kendrion CDR rotary-solenoid brochure](https://www.kendrion.com/fileadmin/user_upload/Downloads/Brochures_and_Flyers/Electromagnets_Actuators/Compact-rotary-solenoid-CDR-Kendrion-EN.pdf):
  bistable rotary designs with up to 90-degree travel; not evidence of Sri Lankan pricing.
- [TowerPro SG90](https://towerpro.com.tw/product/sg90-7/): example manufacturer
  specifications include a 4.8 V supply and 0.1 s/60-degree no-load operating speed.
  Local generic products must be tested rather than assumed to match this genuine model.
- [Adafruit small solenoid](https://www.adafruit.com/product/2776): illustrates
  spring-return linear motion, high coil current, transistor and protection-diode needs;
  its specific 5 V model is not the Tronic part.
- [Adafruit PCA9685 guide](https://learn.adafruit.com/16-channel-pwm-servo-driver/overview):
  16 servo-control channels and I2C board chaining.
- [Dynalloy wire data](https://dynalloy.com/technical-data-wires/): shape-memory
  wire actuation depends on heating/cooling and wire size, not instantaneous voltage-to-angle motion.

## Architecture and prototype implications

A grid that independently closes arbitrary cells for multiple eye/light intersections
needs independent cell control, or a demonstrated addressing/latching mechanism.
Rows and columns alone do not automatically provide that behaviour: moving whole
strips may shade unrelated areas. If 17-50 refers to row/column bars, rather than
individual flaps, the actuator count and spatial behaviour need a separate design.

Use a 2x2 sample before scaling: cycle both positions under load, check return-to-open,
record command-to-motion and optical-blocking delay, test simultaneous cells, jitter,
current, heating, backlash and obstruction by motor bodies. Loaded performance must
not be inferred from a no-load speed listing. A coarse flap grid also introduces cell
quantization/blocking-area error that is different from the continuous LCD mask.

The current Python app still outputs to the LCD. No flap firmware, row/column mechanics,
hardware driver or new servo-control path was added by this research step.
