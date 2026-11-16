VAR knows_trip_cause = false
VAR pack_state = "ready"
VAR crew_rescued = false
VAR medicine_cold = false
VAR incident_receipts = 0

-> ridge_station

=== ridge_station ===
The lift house smells of singed wool. A blue seal crosses the emergency pack's lid.
Ilya taps the selector. "The storm cooked the pack. Don't trust it."
Three circuits still meet at the selector. The lift has one usable crossing before the wind rises. The clinic needs its cooler until dawn. The crew can wait in a bare refuge if they have to.
The pack has one high-draw cycle, or enough current for the refuge heater if that line holds.
* [Read the relay log by the selector. # choice-id: discover-log] -> relay_log
* [Skip the log and go straight to the selector. # choice-id: skip-log] -> selector

=== relay_log ===
~ knows_trip_cause = true
06:12. Heater cable insulation failed. Pack isolated by the fuse.
06:24. Maintenance fitted the last spare fuse and reset isolation. Selector set to neutral.
06:32. Pack capacity check passed. Seal blue.
06:40. First lightning.
You point to the first and last entries. Ilya studies the seal, then clears the warning he chalked over the lift switch.
-> selector

=== selector ===
{knows_trip_cause:
    "The pack is good," Ilya says. "The heater lead still isn't."
- else:
    The pack's reserve needle is green. At the heater terminal, a split in the cable shows copper.
}
* [Power the lift. Get the crew down now and let the clinic cooler warm. # choice-id: power-lift] -> lift
* [Power the cooler. Keep the medicine cold and leave the crew in the refuge. # choice-id: power-cooler] -> cooler
* [Try the refuge heater. Its cracked lead may trip the entire pack. # choice-id: try-heater] -> heater

=== lift ===
~ pack_state = "spent"
~ crew_rescued = true
The far car bumps home. Three night workers step down into the lift house.
At the clinic window, a nurse puts the warmed vials in a tray marked for disposal.
-> report

=== cooler ===
~ pack_state = "spent"
~ medicine_cold = true
A green thermometer lights in the clinic window. The nurse keeps the vials in their rack.
Over the radio, a worker asks Ilya to stay on the channel until the relief crew climbs up at dawn.
-> report

=== heater ===
~ pack_state = "isolated"
The cracked lead sparks. The fuse blows and the pack's isolation latch falls shut. No spare fuse remains.
The refuge stays dark. The nurse lifts the first warming vial out of the cooler.
-> report

=== report ===
{incident_receipts == 0:
    ~ incident_receipts += 1
    Ilya writes one entry for the night shift.
- else:
    The night shift's entry is already in the ledger.
}
+ [Check the ledger again. # choice-id: revisit-logbook] -> report
* [Close the logbook. # choice-id: close-logbook] -> END
