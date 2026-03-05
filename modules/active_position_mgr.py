"""
modules/active_position_mgr.py
APEX PREDATOR NEO v666.1 – APM (see ISHERTHEONE/apm.py for full impl)

4 Weapons of HFT Scalping:
 1. VPIN — Volume-Synchronized Probability of Informed Trading
    VPIN_BUCKET_COUNT=50, TOXIC=0.70, CRITICAL=0.85
 2. Dynamic OBI Trailing — OBI>0.60→3.5xATR, OBI<-0.30→0.8xATR
 3. Ghost Liquidity Reaction — SpoofHunter confidence>60%→exit
 4. Alpha Decay — 180s max hold, must move >=0.5%
Full implementation in the distributed ISHERTHEONE deployment.
"""
