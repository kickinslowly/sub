import re
import pytz
from datetime import datetime, time, timedelta

class TimeRange:
    """
    A class to represent a time range with proper comparison and overlap detection.
    
    This class handles time ranges in various formats:
    - "HH:MM-HH:MM" (24-hour format)
    - "HH:MM AM/PM - HH:MM AM/PM" (12-hour format)
    
    It also properly handles overnight ranges (e.g., "22:00-02:00").
    """
    
    def __init__(self, start_time, end_time, is_24h_format=True):
        """
        Initialize a TimeRange with start and end times.
        
        :param start_time: Start time as a time object or string
        :param end_time: End time as a time object or string
        :param is_24h_format: Whether the time strings are in 24-hour format
        """
        # If strings are provided, parse them
        if isinstance(start_time, str):
            self.start_time = self._parse_time(start_time, is_24h_format)
        else:
            self.start_time = start_time
            
        if isinstance(end_time, str):
            self.end_time = self._parse_time(end_time, is_24h_format)
        else:
            self.end_time = end_time
            
        # Flag to indicate if this is an overnight range
        self.is_overnight = self.end_time < self.start_time
    
    @classmethod
    def from_string(cls, time_range_str):
        """
        Create a TimeRange from a string representation.
        
        :param time_range_str: String in format "HH:MM-HH:MM" or "HH:MM AM/PM - HH:MM AM/PM"
        :return: TimeRange object
        """
        # Check if the time range is in 12-hour format
        is_12h_format = 'AM' in time_range_str.upper() or 'PM' in time_range_str.upper()
        
        # Split the time range string
        if is_12h_format:
            # Handle 12-hour format with AM/PM
            parts = time_range_str.split(' - ')
            if len(parts) != 2:
                raise ValueError(f"Invalid time range format: {time_range_str}")
            
            start_str = parts[0].strip()
            end_str = parts[1].strip()
            
            return cls(start_str, end_str, is_24h_format=False)
        else:
            # Handle 24-hour format
            parts = time_range_str.split('-')
            if len(parts) != 2:
                raise ValueError(f"Invalid time range format: {time_range_str}")
            
            start_str = parts[0].strip()
            end_str = parts[1].strip()
            
            return cls(start_str, end_str, is_24h_format=True)
    
    def _parse_time(self, time_str, is_24h_format=True):
        """
        Parse a time string into a time object.
        
        :param time_str: Time string in format "HH:MM" or "HH:MM AM/PM"
        :param is_24h_format: Whether the time string is in 24-hour format
        :return: time object
        """
        if is_24h_format:
            # Parse 24-hour format
            try:
                return datetime.strptime(time_str, '%H:%M').time()
            except ValueError:
                raise ValueError(f"Invalid time format: {time_str}. Expected 'HH:MM'")
        else:
            # Parse 12-hour format
            try:
                return datetime.strptime(time_str, '%I:%M %p').time()
            except ValueError:
                raise ValueError(f"Invalid time format: {time_str}. Expected 'HH:MM AM/PM'")
    
    def overlaps(self, other):
        """
        Check if this time range overlaps with another time range.
        
        :param other: Another TimeRange object
        :return: True if there's an overlap, False otherwise
        """
        # Handle overnight ranges
        if self.is_overnight and other.is_overnight:
            # Both ranges are overnight, they must overlap
            return True
        elif self.is_overnight:
            # This range is overnight, check if other range overlaps
            return not (other.end_time <= self.start_time and other.start_time >= self.end_time)
        elif other.is_overnight:
            # Other range is overnight, check if this range overlaps
            return not (self.end_time <= other.start_time and self.start_time >= other.end_time)
        else:
            # Neither range is overnight, check for standard overlap
            return self.start_time < other.end_time and self.end_time > other.start_time
    
    def contains(self, time_obj):
        """
        Check if this time range contains a specific time.
        
        :param time_obj: A time object or string
        :return: True if the time is within this range, False otherwise
        """
        if isinstance(time_obj, str):
            # Determine format and parse
            is_12h = 'AM' in time_obj.upper() or 'PM' in time_obj.upper()
            time_obj = self._parse_time(time_obj, not is_12h)
        
        if self.is_overnight:
            # For overnight ranges, check if time is after start or before end
            return time_obj >= self.start_time or time_obj <= self.end_time
        else:
            # For standard ranges, check if time is between start and end
            return self.start_time <= time_obj <= self.end_time
    
    def __str__(self):
        """
        Return a string representation of the time range in 24-hour format.
        
        :return: String in format "HH:MM-HH:MM"
        """
        return f"{self.start_time.strftime('%H:%M')}-{self.end_time.strftime('%H:%M')}"
    
    def to_12h_format(self):
        """
        Return a string representation of the time range in 12-hour format.
        
        :return: String in format "HH:MM AM/PM - HH:MM AM/PM"
        """
        return f"{self.start_time.strftime('%I:%M %p')} - {self.end_time.strftime('%I:%M %p')}"


def parse_time_range(time_range_str):
    """
    Parse a time range string into a TimeRange object.
    
    :param time_range_str: String in format "HH:MM-HH:MM" or "HH:MM AM/PM - HH:MM AM/PM"
    :return: TimeRange object
    """
    return TimeRange.from_string(time_range_str)


def check_time_range_overlap(range1_str, range2_str):
    """
    Check if two time range strings overlap.
    
    :param range1_str: First time range string
    :param range2_str: Second time range string
    :return: True if there's an overlap, False otherwise
    """
    range1 = parse_time_range(range1_str)
    range2 = parse_time_range(range2_str)
    return range1.overlaps(range2)


def convert_time_format(time_str, to_24h=True):
    """
    Convert a time string between 12-hour and 24-hour formats.
    
    :param time_str: Time string to convert
    :param to_24h: True to convert to 24-hour format, False to convert to 12-hour format
    :return: Converted time string
    """
    # Determine current format
    is_12h = 'AM' in time_str.upper() or 'PM' in time_str.upper()
    
    if is_12h and to_24h:
        # Convert from 12h to 24h
        time_obj = datetime.strptime(time_str, '%I:%M %p').time()
        return time_obj.strftime('%H:%M')
    elif not is_12h and not to_24h:
        # Convert from 24h to 12h
        time_obj = datetime.strptime(time_str, '%H:%M').time()
        return time_obj.strftime('%I:%M %p')
    else:
        # Already in the requested format
        return time_str


def get_current_time_in_timezone(timezone_str):
    """
    Get the current time in the specified timezone.
    
    :param timezone_str: Timezone string (e.g., 'America/New_York')
    :return: Current datetime in the specified timezone
    """
    if timezone_str is None:
        timezone_str = 'UTC'
    
    try:
        tz = pytz.timezone(timezone_str)
        return datetime.now(tz)
    except Exception:
        # Fall back to UTC if there's an error
        return datetime.now(pytz.UTC)


def localize_datetime(dt, timezone_str):
    """
    Localize a naive datetime to the specified timezone.
    
    :param dt: Naive datetime object
    :param timezone_str: Timezone string (e.g., 'America/New_York')
    :return: Timezone-aware datetime object
    """
    if timezone_str is None:
        timezone_str = 'UTC'
    
    try:
        tz = pytz.timezone(timezone_str)
        if dt.tzinfo is None:
            return tz.localize(dt)
        else:
            return dt.astimezone(tz)
    except Exception:
        # Fall back to UTC if there's an error
        if dt.tzinfo is None:
            return pytz.UTC.localize(dt)
        else:
            return dt.astimezone(pytz.UTC)