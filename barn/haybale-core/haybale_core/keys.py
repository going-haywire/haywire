"""Registry keys of haybale-core components that other code names by string.

Leaf module by design: no imports, so a node can bind its widget or skin
without importing the NiceGUI-backed class. ``tests/barn/test_haybale_core_keys.py``
checks each constant against the class it names.
"""

ARRAY_WIDGET = "haybale-core:widget:ArrayWidget"
WIDGET_NODE_SKIN = "haybale-core:skin:WidgetNodeSkin"
