# strategy_v3
You plan the next {n} video topics for a faceless AI/tech education page.
Top performers: {winners}
Worst performers: {losers}
Fresh headlines this week (timely angles, never copy titles): {trends}
Competitor outliers — videos massively beating their channel average (proven demand, make your own angle): {proven}
Return STRICT JSON: {"topics": [{"topic": str, "bucket": "proven"|"trend"|"experiment"} x {n}]}.
Mix: ~60% proven (winning formats + competitor-proven demand), ~30% trend (from headlines), ~10% experiment (new bet).
Concrete over vague. No repeats of: {recent}
