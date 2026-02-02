import calendar
import logging
from datetime import datetime, timedelta, timezone
# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


class NewsFilter:
    """News filter to avoid trading during major economic events"""

    def __init__(self):
        """Initialize news filter with default configuration"""
        self.enabled = True
        self.major_events_only = True
        self.avoid_events = ["NFP", "CPI", "PPI", "FOMC"]
        self.buffer_minutes = 30

    def load_config(self, config):
        """Load configuration from set file"""
        try:
            if "news_filter" in config:
                nf_config = config["news_filter"]
                self.enabled = nf_config.get("enabled", True)
                self.major_events_only = nf_config.get("major_events_only", True)
                self.avoid_events = nf_config.get(
                    "avoid_events", ["NFP", "CPI", "PPI", "FOMC"],
                )
                self.buffer_minutes = nf_config.get("buffer_minutes", 30)
                logger.info("News filter configuration loaded successfully")
        except Exception as e:
            logger.warning(f"Failed to load news filter configuration: {e}")

    def is_first_friday(self, date):
        """Check if date is the first Friday of the month"""
        # First day of month
        first_day = date.replace(day=1)
        # Find first Friday
        first_friday = first_day + timedelta(days=(4 - first_day.weekday()) % 7)
        return date.date() == first_friday.date()

    def is_news_time(self):
        """
        Check if current time is near a major economic event
        Returns True if there's an important event within buffer_minutes
        """
        if not self.enabled:
            return False

        now = datetime.now(timezone.utc)

        # Check different economic events
        if self._check_nfp_event(now):
            return True

        if self._check_cpi_event(now):
            return True

        if self._check_ppi_event(now):
            return True

        if self._check_fomc_event(now):
            return True

        return False

    def _check_nfp_event(self, now):
        """Check for Non-Farm Payrolls event."""
        if "NFP" not in self.avoid_events or not self.is_first_friday(now):
            return False

        return self._is_event_time(now, "13:30", "NFP")

    def _check_cpi_event(self, now):
        """Check for Consumer Price Index event."""
        if "CPI" not in self.avoid_events or not (13 <= now.day <= 17):
            return False

        return self._is_event_time(now, "13:30", "CPI")

    def _check_ppi_event(self, now):
        """Check for Producer Price Index event."""
        if "PPI" not in self.avoid_events or not (13 <= now.day <= 17):
            return False

        return self._is_event_time(now, "13:30", "PPI")

    def _check_fomc_event(self, now):
        """Check for Federal Open Market Committee event."""
        if "FOMC" not in self.avoid_events:
            return False

        # FOMC typically occurs on Wednesdays, last two weeks of month
        if now.weekday() != 2:  # Not Wednesday
            return False

        last_day = calendar.monthrange(now.year, now.month)[1]
        if now.day <= last_day - 14:  # Not in last two weeks
            return False

        return self._is_event_time(now, "19:00", "FOMC")

    def _is_event_time(self, now, event_time_str, event_name):
        """Check if current time is near the specified event time."""
        event_time = datetime.strptime(event_time_str, "%H:%M").time()
        event_datetime = datetime.combine(now.date(), event_time)
        time_diff = abs((now - event_datetime).total_seconds() / 60)

        if time_diff <= self.buffer_minutes:
            logger.info(f"{event_name} event detected")
            return True
        return False


# Global instance
news_filter = NewsFilter()
