import logging
from datetime import datetime, timedelta
import calendar

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
                    "avoid_events", ["NFP", "CPI", "PPI", "FOMC"]
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

        now = datetime.utcnow()

        # Check for NFP (First Friday of month at 13:30 UTC)
        if "NFP" in self.avoid_events and self.is_first_friday(now):
            nfp_time = datetime.strptime("13:30", "%H:%M").time()
            nfp_datetime = datetime.combine(now.date(), nfp_time)
            time_diff = abs((now - nfp_datetime).total_seconds() / 60)
            if time_diff <= self.buffer_minutes:
                logger.info("NFP event detected")
                return True

        # Check for CPI (Monthly around 15th at 13:30 UTC)
        if "CPI" in self.avoid_events and 13 <= now.day <= 17:
            cpi_time = datetime.strptime("13:30", "%H:%M").time()
            cpi_datetime = datetime.combine(now.date(), cpi_time)
            time_diff = abs((now - cpi_datetime).total_seconds() / 60)
            if time_diff <= self.buffer_minutes:
                logger.info("CPI event detected")
                return True

        # Check for PPI (Monthly around 15th at 13:30 UTC)
        if "PPI" in self.avoid_events and 13 <= now.day <= 17:
            ppi_time = datetime.strptime("13:30", "%H:%M").time()
            ppi_datetime = datetime.combine(now.date(), ppi_time)
            time_diff = abs((now - ppi_datetime).total_seconds() / 60)
            if time_diff <= self.buffer_minutes:
                logger.info("PPI event detected")
                return True

        # Check for FOMC (typically 2x per month, Wednesdays)
        # Simplified check for FOMC days
        if "FOMC" in self.avoid_events:
            # FOMC typically occurs on Wednesdays, last two weeks of month
            if now.weekday() == 2:  # Wednesday
                last_day = calendar.monthrange(now.year, now.month)[1]
                if now.day > last_day - 14:  # Last two weeks
                    fomc_time = datetime.strptime("19:00", "%H:%M").time()
                    fomc_datetime = datetime.combine(now.date(), fomc_time)
                    time_diff = abs((now - fomc_datetime).total_seconds() / 60)
                    if time_diff <= self.buffer_minutes:
                        logger.info("FOMC event detected")
                        return True

        return False


# Global instance
news_filter = NewsFilter()
