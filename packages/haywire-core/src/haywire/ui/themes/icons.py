"""
Named color constants and unified theme keys for Haywire.
"""

from typing import Final

class ICONS:
    """
    Hardcoded icon name constants with IDE preview support.
    see https://fonts.google.com/icons?icon.set=Material%20Icons
    """
    
    # Basic icons
    MY_LOCATION: Final[str] = "my_location"
    LABEL_IMPORTANT: Final[str] = "label_important"
    LABEL: Final[str] = "label"
    CIRCLE: Final[str] = "circle"
    ADD_CIRCLE: Final[str] = "add_circle"
    BOX: Final[str] = "box"
    ADD_BOX: Final[str] = "add_box"
    CONTRAST: Final[str] = "contrast"
    PENTAGON: Final[str] = "pentagon"
    PENDING: Final[str] = "pending"
    VIEW_HEADLINE: Final[str] = "view_headline"
    TOC: Final[str] = "toc"
    VIEW_MODULE: Final[str] = "view_module"
    API: Final[str] = "api"
    APPS: Final[str] = "apps"
    VIEW_AGENDA: Final[str] = "view_agenda"
    VIEW_SIDEBAR: Final[str] = "view_sidebar"
    VERTICAL_SPLIT: Final[str] = "vertical_split"
    CALENDAR_VIEW_DAY: Final[str] = "calendar_view_day"
    SQUARE: Final[str] = "square"
    VIEW_DAY: Final[str] = "view_day"
    VIEW_ARRAY: Final[str] = "view_array"
    JOIN_LEFT: Final[str] = "join_left"
    JOIN_RIGHT: Final[str] = "join_right"
    WEB_STORIES: Final[str] = "web_stories"
    VIEW_COMFY: Final[str] = "view_comfy"
    STAY_PRIMARY_LANDSCAPE: Final[str] = "stay_primary_landscape"
    LOCAL_PLAY: Final[str] = "local_play"
    GRID_VIEW: Final[str] = "grid_view"
    PLAY_ARROW: Final[str] = "play_arrow"
    VIDEOCAM: Final[str] = "videocam"
    SKIP_NEXT: Final[str] = "skip_next"
    FAST_FORWARD: Final[str] = "fast_forward"
    SUBSCRIPTIONS: Final[str] = "subscriptions"
    CONTROL_CAMERA: Final[str] = "control_camera"
    CALL_TO_ACTION: Final[str] = "call_to_action"
    TORNADO: Final[str] = "tornado"
    EAST: Final[str] = "east"
    WEST: Final[str] = "west"
    SOUTH: Final[str] = "south"
    NORTH: Final[str] = "north"
    HIVE: Final[str] = "hive"
    RADIO_BUTTON_CHECKED: Final[str] = "radio_button_checked"
    WARNING: Final[str] = "warning"
    ERROR: Final[str] = "error"
    BORDER_INNER: Final[str] = "border_inner"
    BORDER_CLEAR: Final[str] = "border_clear"
    KEYBOARD_DOUBLE_ARROW_RIGHT: Final[str] = "keyboard_double_arrow_right"
    KEYBOARD_DOUBLE_ARROW_LEFT: Final[str] = "keyboard_double_arrow_left"
    GAMEPAD: Final[str] = "gamepad"
    GRID_4X4: Final[str] = "grid_4x4"
    FIBER_SMART_RECORD: Final[str] = "fiber_smart_record"
    SWIPE_LEFT_ALT: Final[str] = "swipe_left_alt"
    SWIPE_RIGHT_ALT: Final[str] = "swipe_right_alt"

    @classmethod
    def get(cls, name: str, default: str = "circle") -> str:
        """
        Get icons by name with fallback.
        
        Args:
            name: Icon name (case-insensitive)
            default: Fallback icon if name not found
            
        Returns:
            Icon value as string
        """
        # Convert name to uppercase
        normalized_name = name.upper()
        
        # Check if attribute exists
        if hasattr(cls, normalized_name):
            return getattr(cls, normalized_name)
        
        # Return default
        return default