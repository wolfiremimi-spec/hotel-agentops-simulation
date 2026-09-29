from product import tour
H.clicks.add("ha_demo"); run(); t = text()
H.nav_target = "product/views/decision_log.py"; run()
H.nav_target = "product/views/today.py"; run()
date = "2026-10-03"
H.clicks.add("Save this morning's data and ask the agents"); run(); t = text()
radios = [k for k in H.session_state if k.startswith("td_ch_")]
for k in radios: H.values[k] = "Approve"
H.clicks.add(f"td_submit_{date}"); run(); t = text()
H.clicks.add(f"td_goto_co_{date}"); run(); t = text()
H.clicks.add(f"co_fill_{date}"); run(); H.clicks.add("Save the close-out"); run()
H.nav_target = "product/views/decision_log.py"; run(); t = text()
H.nav_target = "product/views/performance.py"; run(); t = text()
H.nav_target = "product/views/orders.py"; run(); t = text()
H.clicks.add("Approve and log this order"); run(); t = text()
