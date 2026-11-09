# Legacy course scripts

The original assignment submissions, unchanged:

| File | Level | Adds |
|---|---|---|
| `1_1.py` | 1 | base model: booking, fee quote, diversion, towing, 3 crane teams, restacking, customs, barges |
| `2_1.py` | 2 | reporting: turnaround time, diversion rates, restacking hours, plot |
| `3_1.py` | 3 | recorded arrivals (`ship_arrival_information.json`), warm-up, replications, investment comparison |
| `4_1.py` | 4 | parallel container scan + paper check, security alerts that interrupt the scan |

Run one from this folder (`3_1.py` reads the JSON file from the working directory):

```bash
cd legacy && pip install simpy matplotlib && python 3_1.py
```

The maintained implementation is in [`src/terminalsim`](../src/terminalsim). Run
`python tools/compare_with_legacy.py` from the repository root to check that both produce statistically
equivalent results.
