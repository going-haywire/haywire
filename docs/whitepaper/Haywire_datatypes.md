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

[color](https://nicegui.io/documentation/color_input)

has no alpha support

```python
from nicegui import ui

label = ui.label('Change my color!')
ui.color_input(label='Color', value='#000000',
               on_change=lambda e: label.style(f'color:{e.value}'))

ui.run()
```

[data picker](https://nicegui.io/documentation/date)

```python
from nicegui import ui

ui.date(label='Date', value='2022-01-01',
        on_change=lambda e: result.set_text(f'you selected: {e.value}'))
result = ui.label()

ui.run()
```

[date picker](https://nicegui.io/documentation/date)

```python
from nicegui import ui

with ui.input('Date') as date:
    with ui.menu().props('no-parent-event') as menu:
        with ui.date().bind_value(date):
            with ui.row().classes('justify-end'):
                ui.button('Close', on_click=menu.close).props('flat')
    with date.add_slot('append'):
        ui.icon('edit_calendar').on('click', menu.open).classes('cursor-pointer')

ui.run()
```

[date range picker](https://nicegui.io/documentation/date)

```python
from nicegui import ui

date_input = ui.input('Date range').classes('w-40')
ui.date().props('range').bind_value(
    date_input,
    forward=lambda x: f'{x["from"]} - {x["to"]}' if x else None,
    backward=lambda x: {
        'from': x.split(' - ')[0],
        'to': x.split(' - ')[1],
    } if ' - ' in (x or '') else None,
)

ui.run()
```

[time picker](https://nicegui.io/documentation/time)

```python
from nicegui import ui

with ui.input('Time') as time:
    with ui.menu().props('no-parent-event') as menu:
        with ui.time().bind_value(time):
            with ui.row().classes('justify-end'):
                ui.button('Close', on_click=menu.close).props('flat')
    with time.add_slot('append'):
        ui.icon('access_time').on('click', menu.open).classes('cursor-pointer')

ui.run()
```

## Bindings to model properties

[Bindings](https://nicegui.io/documentation/section_binding_properties#bindings)

NiceGUI is able to directly bind UI elements to models. Binding is possible for UI element properties like text, value or visibility and for model properties that are (nested) class attributes. Each element provides methods like bind_value and bind_visibility to create a two-way binding with the corresponding property. To define a one-way binding use the _from and _to variants of these methods. Just pass a property of the model as parameter to these methods to create the binding. The values will be updated immediately and whenever one of them changes.

```python
from nicegui import ui

class Demo:
    def __init__(self):
        self.number = 1

demo = Demo()
v = ui.checkbox('visible', value=True)
with ui.column().bind_visibility_from(v, 'value'):
    ui.slider(min=1, max=3).bind_value(demo, 'number')
    ui.toggle({1: 'A', 2: 'B', 3: 'C'}).bind_value(demo, 'number')
    ui.number().bind_value(demo, 'number')

ui.run()
```

[Transformation functions](https://nicegui.io/documentation/section_binding_properties#transformation_functions)

You can use forward and backward transformation functions to convert the value when propagating it from one object to another. These functions are called whenever the source attribute changes, or - in case of active links (see below) - whenever the source attribute is checked for changes.
NiceGUI is strictly adhering to a Depth-First-Search approach, updating every affected node once and executing the transformation function once. For the most stable behaviour across releases, it is best-practice that transform functions have no side-effects and do basic transform operations only. This way, it will not matter how NiceGUI chooses to call them in what order and by how many times.

```python
from nicegui import ui

i = ui.input(value='Lorem ipsum')
ui.label().bind_text_from(i, 'value',
                          backward=lambda text: f'{len(text)} characters')

ui.run()
```

[Bind to dictionary](https://nicegui.io/documentation/section_binding_properties#bind_to_dictionary)

Here we are binding the text of labels to a dictionary.

```python
from nicegui import ui

data = {'name': 'Bob', 'age': 17}

ui.label().bind_text_from(data, 'name', backward=lambda n: f'Name: {n}')
ui.label().bind_text_from(data, 'age', backward=lambda a: f'Age: {a}')

ui.button('Turn 18', on_click=lambda: data.update(age=18))

ui.run()
```

[Binding for optimal performance](https://nicegui.io/documentation/section_binding_properties#bindable_properties_for_maximum_performance)

There are two types of bindings:

* "Bindable properties" automatically detect write access and trigger the value propagation. Most NiceGUI elements use these bindable properties, like value in ui.input or text in ui.label. Basically all properties with bind() methods support this type of binding.
* All other bindings are sometimes called "active links". If you bind a label text to some dictionary entry or an attribute of a custom data model, NiceGUI's binding module has to actively check if the value changed. This is done in a refresh_loop() which runs every 0.1 seconds. The interval can be configured via binding_refresh_interval in ui.run().

The "bindable properties" are very efficient and don't cost anything as long as the values don't change. But the "active links" need to check all bound values 10 times per second. This can get costly, especially if you bind to complex objects like lists or dictionaries.

Because it is crucial not to block the main thread for too long, we show a warning if one step of the refresh_loop() takes too long. You can configure the threshold via binding.MAX_PROPAGATION_TIME which defaults to 0.01 seconds. But often the warning is a valuable indicator for a performance or memory issue. If your CPU would be busy updating bindings a significant duration, nothing else could happen on the main thread and the UI "hangs".

The following demo shows how to define and use bindable properties for a Demo class like in the first demo. The number property is now a BindableProperty, which allows NiceGUI to detect write access and trigger the value propagation immediately.

```python
from nicegui import binding, ui

class Demo:
    number = binding.BindableProperty()

    def __init__(self):
        self.number = 1

demo = Demo()
ui.slider(min=1, max=3).bind_value(demo, 'number')
ui.toggle({1: 'A', 2: 'B', 3: 'C'}).bind_value(demo, 'number')
ui.number(min=1, max=3).bind_value(demo, 'number')

ui.run()
```

The bindable_dataclass decorator provides a convenient way to create classes with bindable properties.

```python
from nicegui import binding, ui

@binding.bindable_dataclass
class Demo:
    number: int = 1

demo = Demo()
ui.slider(min=1, max=3).bind_value(demo, 'number')
ui.toggle({1: 'A', 2: 'B', 3: 'C'}).bind_value(demo, 'number')
ui.number(min=1, max=3).bind_value(demo, 'number')

ui.run()
``
