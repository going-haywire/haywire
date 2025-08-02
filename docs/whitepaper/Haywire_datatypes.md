## niceGUI UI Elements to consider:

[range](https://nicegui.io/documentation/range#range)

```python
from nicegui import ui

min_max_range = ui.range(min=0, max=100, value={'min': 20, 'max': 80})
ui.label().bind_text_from(min_max_range, 'value',
                          backward=lambda v: f'min: {v["min"]}, max: {v["max"]}')

ui.run()
```

[slider](https://nicegui.io/documentation/slider#slider)

```python
from nicegui import ui

slider = ui.slider(min=0, max=100, value=50)
ui.label().bind_text_from(slider, 'value')

ui.run()
```

[switch](https://nicegui.io/documentation/switch#switch)

```python
from nicegui import ui

switch = ui.switch('switch me')
ui.label('Switch!').bind_visibility_from(switch, 'value')

ui.run()
```

[checkbox](https://nicegui.io/documentation/checkbox#checkbox)

```python
from nicegui import ui

checkbox = ui.checkbox('check me')
ui.label('Check!').bind_visibility_from(checkbox, 'value')

ui.run()
```

[input_chips](https://nicegui.io/documentation/input_chips#input_chips)

```python
from nicegui import ui

ui.input_chips('My favorite chips', value=['Pringles', 'Doritos', "Lay's"], new_value_mode='add-unique')

ui.run()
```

[dropdown_selection](https://nicegui.io/documentation/select#dropdown_selection)

```python
from nicegui import ui

ui.select(['Option 1', 'Option 2', 'Option 3'], value='Option 1')

ui.run()
```

[radio_selection](https://nicegui.io/documentation/radio#radio_selection)

```python
from nicegui import ui

radio1 = ui.radio([1, 2, 3], value=1).props('inline')
radio2 = ui.radio({1: 'A', 2: 'B', 3: 'C'}).props('inline').bind_value(radio1, 'value')

ui.run()
```

[toggle](https://nicegui.io/documentation/toggle#toggle)

```python
from nicegui import ui

toggle1 = ui.toggle([1, 2, 3], value=1)
toggle2 = ui.toggle({1: 'A', 2: 'B', 3: 'C'}).bind_value(toggle1, 'value')

ui.run()
```

[button](https://nicegui.io/documentation/button#button)

```python
from nicegui import ui

ui.button('Click me!', on_click=lambda: ui.notify('You clicked me!'))

ui.run()
```

[input](https://nicegui.io/documentation/input)

```python
from nicegui import ui

ui.input(label='Text', placeholder='start typing',
         on_change=lambda e: result.set_text('you typed: ' + e.value),
         validation={'Input too long': lambda value: len(value) < 20})
result = ui.label()

ui.run()
```

[textarea](https://nicegui.io/documentation/textarea)

```python
from nicegui import ui

ui.textarea(label='Text', placeholder='start typing',
            on_change=lambda e: result.set_text('you typed: ' + e.value))
result = ui.label()

ui.run()
```

[number](https://nicegui.io/documentation/number)

```python
from nicegui import ui

ui.number(label='Number', value=3.1415927, format='%.2f',
          on_change=lambda e: result.set_text(f'you entered: {e.value}'))
result = ui.label()

ui.run()
```

[knob](https://nicegui.io/documentation/knob#knob)

```python
from nicegui import ui

knob = ui.knob(0.3, show_value=True)

with ui.knob(color='orange', track_color='grey-2').bind_value(knob, 'value'):
    ui.icon('volume_up')

ui.run()
```
