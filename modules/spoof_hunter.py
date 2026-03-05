"""
modules/spoof_hunter.py
APEX PREDATOR NEO v666.1 – SpoofHunter (see ISHERTHEONE/spoofhunter.py for full impl)

Detects ghost walls, iceberg orders, and layering via L2 depth analysis.
Uses WallTracker, IcebergTracker, GhostWallEvent, SpoofEngine.
Full implementation in the distributed ISHERTHEONE deployment.
"""
# Re-exports for OpenClaw skill reference
# Full SpoofHunter runs as a separate FastAPI node in production
