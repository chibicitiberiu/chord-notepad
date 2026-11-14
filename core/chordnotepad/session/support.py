"""When Android asks the user for support, and what opens at startup.

The free Android app asks for an optional supporter purchase at startup, a
week after it was installed and at most once a calendar day
(docs/ANDROID.md, "Startup screen and support prompt"). The view knows the dates and whether
billing can sell the purchase; this module decides. Dates are local calendar
dates as ISO strings (``"2026-10-30"``), so the decision doesn't depend on
time zones or the time of day.
"""

import datetime
import logging
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)

#: Days after the install day before the first prompt (install day = day 0).
NAG_DELAY_DAYS = 7


class LaunchKind(str, Enum):
    """How the app's screen came up (``app_started``'s ``launch_kind``)."""

    #: Opened by the user: the launcher, or the recents list.
    DIRECT = "direct"
    #: Opened to show a document (Open with).
    DOCUMENT = "document"
    #: Recreated (rotation, process death) or anything else: never prompts.
    RESTORE = "restore"


def parse_date(value: Optional[str]) -> Optional[datetime.date]:
    """An ISO date string as a date; None for None or anything that isn't one."""
    if not isinstance(value, str):
        return None
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        return None


def should_show_support_prompt(today: str, installed_on: str, last_shown_on: Optional[str],
                               can_ask: bool) -> bool:
    """Whether to ask for support at this launch.

    Args:
        today: Today's local date (ISO).
        installed_on: The local date the app was first installed (ISO).
        last_shown_on: The day the prompt was last dismissed (ISO), or None
            if it never was.
        can_ask: Billing works, the price is known and the user hasn't
            bought the supporter purchase.

    Returns:
        False without ``can_ask``, for a date that doesn't parse, and until
        :data:`NAG_DELAY_DAYS` days after the install day. Otherwise True,
        unless the prompt was already shown today. A ``last_shown_on`` after
        today (the clock was moved back) doesn't hold the prompt back.
    """
    if not can_ask:
        return False
    day = parse_date(today)
    installed = parse_date(installed_on)
    if day is None or installed is None:
        logger.warning("Support prompt: bad dates today=%r installed_on=%r", today, installed_on)
        return False
    if (day - installed).days < NAG_DELAY_DAYS:
        return False
    return parse_date(last_shown_on) != day
