"""CLI entry points for the financial analyst agent.

These thin wrappers let installed console scripts delegate to the
root-level pipeline scripts while keeping those scripts independently
runnable via `uv run python <script>.py`.
"""

import argparse
import os
import sys

# Ensure the project root is on sys.path so root-level modules are importable
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


def pipeline():
    """fin-pipeline: Run the full notebook pipeline + Supabase sync."""
    from run_pipeline import main
    main()


def sync():
    """fin-sync: Push the latest pipeline output to Supabase."""
    from sync_to_supabase import main
    parser = argparse.ArgumentParser(description="Sync pipeline output to Supabase")
    parser.add_argument(
        "--trigger",
        choices=["scheduled", "manual"],
        default="manual",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-sync even if this run was already synced",
    )
    args = parser.parse_args()
    main(trigger=args.trigger, force=args.force)


def poller():
    """fin-poller: Start the refresh-request polling daemon."""
    from poll_refresh import main
    parser = argparse.ArgumentParser(description="Poll for dashboard refresh requests")
    parser.add_argument("--once", action="store_true", help="Poll once and exit")
    args = parser.parse_args()
    main(once=args.once)


def server():
    """fin-server: Start the Plaid Link Flask server (account setup)."""
    from server import app, load_tokens
    load_tokens()
    app.run(port=5000, debug=False)
