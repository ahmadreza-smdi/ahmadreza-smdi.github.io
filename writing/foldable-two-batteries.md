Wait, That’s Tech? · Battery design

# Two batteries, one foldable phone: how the battery reading works

A foldable phone can use two batteries to fit around its hinge while showing one charge reading. That reading estimates usable energy across the system; averaging the two percentages can mislead.

Continue reading: [Tech, explained](https://a-samadi.com/topics/tech-explained.html) · [Signature ideas](https://a-samadi.com/ideas.html)

By [Ahmadreza Samadi](https://a-samadi.com/about.html) · 3 October 2026

Updated 19 October 2026

## At a glance

A combined battery reading estimates usable energy across the system. Capacity, load, temperature and health can matter, so simply averaging two percentages can mislead. The worked numbers below are illustrative; one icon does not reveal the device’s wiring or balancing algorithm.

## Why split the battery?

A folding hinge interrupts the space that an ordinary flat phone can use. Apple says its announced iPhone Duo places one high-energy battery on each side and uses Apple silicon and “energy rebalancing algorithms” to make them operate seamlessly as one. That confirms the two-battery design and the stated software-level goal. The announcement does not publish a detailed circuit diagram or the exact control algorithm, so the explanation below is about the general principle, not a teardown of iPhone Duo.

## How does one reading combine two stores of energy?

The phone needs to estimate how much usable energy remains in the system. Battery fuel gauges do more than read an instantaneous voltage: they estimate state of charge and health using models that can account for capacity, load, resistance and temperature. The phone can then present a single system-level reading while managing charging and power use behind the scenes. The exact physical connection and balancing strategy depend on the product design.

Why not just average the two displayed percentages? Suppose an illustrative battery A can store 12 watt-hours and is half full, while battery B can store 8 watt-hours and is full. In this example, 50% means half the energy stored when the battery is fully charged; a real phone’s displayed charge percentage may be calculated differently. They hold about 6 + 8 = 14 watt-hours out of 20, or 70% of their combined nominal energy. Averaging 50% and 100% would say 75% and overstate the total. These are made-up numbers, not iPhone Duo specifications. Real remaining-runtime estimates also depend on load, battery health and what part of the stored energy is usable.

## What can’t one battery icon tell you?

One icon makes the device easier to use, but it does not reveal each pack’s capacity, charge level or health. Nor does it prove the two packs are wired in series, in parallel or through a particular converter. Those details require product-specific documentation or a reliable teardown. The clear distinction is this: Apple confirms two batteries and energy rebalancing; the capacity-weighted example explains why a combined reading needs more thought than averaging two percentages.

## See the original explanation

My [Instagram carousel](https://www.instagram.com/p/DeAhR0PCqaa/) and [LinkedIn document post](https://www.linkedin.com/feed/update/urn:li:activity:7511910075654070272/) show the hinge constraint and the illustrative percentage example as short visual walkthroughs.

## Sources

- [Apple: iPhone Duo announcement, 9 September 2026](https://www.apple.com/newsroom/2026/09/apple-unveils-iphone-duo/)

- [Texas Instruments: battery fuel gauges and state-of-charge estimation](https://www.ti.com/product-category/battery-management-ics/battery-fuel-gauges/overview.html)

- [Texas Instruments: charge and energy reporting (section 2.7, PDF)](https://www.ti.com/lit/SLUA364)
