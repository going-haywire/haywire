from nicegui import ui
from popup import Popup


# Example usage functions
def show_settings_modal():
    """Example: Settings modal"""
    popup_instance = Popup(title="Settings", width="500px", closable=True)
    
    with popup_instance:
        ui.label("Configure your preferences:")
        ui.separator()
        
        with ui.column().classes('w-full gap-4'):
            ui.input('Username', placeholder='Enter username')
            ui.input('Email', placeholder='Enter email')
            ui.switch('Enable notifications')
            ui.slider(min=0, max=100, value=50).props('label="Volume"')
            
        ui.separator()
        
        with ui.row().classes('w-full justify-end gap-2'):
            ui.button('Cancel', on_click=lambda: popup_instance.close()).props('flat')
            ui.button(
                'Save', 
                on_click=lambda: (
                    ui.notify('Settings saved!'), popup_instance.close()
                )
            )
    
    popup_instance.open()

def show_confirmation_modal():
    """Example: Confirmation modal"""
    popup_instance = Popup(title="Confirm Action", width="350px", backdrop_click_close=False)
    
    with popup_instance:
        ui.label("Are you sure you want to delete this item?")
        ui.label("This action cannot be undone.").style('color: #666; font-size: 0.9em;')
        
        ui.separator()
        
        with ui.row().classes('w-full justify-end gap-2'):
            ui.button('Cancel', on_click=lambda: popup_instance.close()).props('flat')
            ui.button(
                'Delete', 
                on_click=lambda: (
                    ui.notify('Item deleted!'), popup_instance.close()
                )
            ).props('color=negative')
    
    popup_instance.open()

def show_form_modal():
    """Example: Form modal"""
    popup_instance = Popup(title="Add New Item", width="600px", height="400px")
    
    with popup_instance:
        with ui.column().classes('w-full gap-4'):
            ui.input('Title', placeholder='Enter title').classes('w-full')
            ui.textarea('Description', placeholder='Enter description').classes('w-full')
            ui.select(['Option 1', 'Option 2', 'Option 3'], label='Category').classes('w-full')
            ui.upload(label='Upload file', auto_upload=True).classes('w-full')
            
        ui.separator()
        
        with ui.row().classes('w-full justify-between'):
            ui.button('Reset Form', on_click=lambda: ui.notify('Form reset')).props('flat')
            with ui.row().classes('gap-2'):
                ui.button('Cancel', on_click=lambda: popup_instance.close()).props('flat')
                ui.button(
                    'Create', 
                    on_click=lambda: (
                        ui.notify('Item created!'), popup_instance.close()
                    )
                )

    popup_instance.open()

def show_custom_styled_modal():
    """Example: Custom styled modal"""
    popup_instance = Popup(
        title="Custom Styled Modal",
        backdrop_color="rgba(25, 25, 112, 0.7)",  # Dark blue backdrop
        closable=True
    )
    
    with popup_instance as popup:
        # Custom styling for the content
        popup.style('background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white;')
        
        ui.label("This modal has custom styling!").style('font-size: 1.1em; color: white;')
        ui.separator().style('background-color: rgba(255,255,255,0.3);')
        
        ui.label("You can customize colors, gradients, and more.")
        
        with ui.row().classes('w-full justify-center mt-4'):
            ui.button(
                'Close', 
                on_click=lambda: popup_instance.close()
            ).style(
                'background: rgba(255,255,255,0.2); color: white;'
            )
    
    # Set a close callback
    popup_instance.on_close(lambda: ui.notify('Custom modal closed!'))
    popup_instance.open()


# Demo application
if __name__ in {"__main__", "__mp_main__"}:
    ui.label(
        'Custom Modal Component Demo'
    ).style('font-size: 1.5em; font-weight: bold; margin-bottom: 20px;')
    
    with ui.row().classes('gap-4'):
        ui.button('Settings Modal', on_click=show_settings_modal)
        ui.button('Confirmation Modal', on_click=show_confirmation_modal)
        ui.button('Form Modal', on_click=show_form_modal)
        ui.button('Custom Styled Modal', on_click=show_custom_styled_modal)
    
    ui.separator()
    ui.label('Click any button to see different modal examples!')
    
    ui.run()